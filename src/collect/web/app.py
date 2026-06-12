"""Flask adapter over the service layer.

Thin: every route parses the request, calls the service, and renders. No
business logic lives here. Hardened for local use with a persisted secret key,
a lightweight per-session CSRF token on every POST, and flash messaging.

Tabs: My Collection (showcase, ``/``), Manage Collection (``/manage``),
Wishlist (``/wishlist``).
"""

from __future__ import annotations

import os
import secrets
import sys
from functools import wraps

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for,
)

from .. import currency
from ..config import home_dir
from ..errors import CollectError
from ..model import PRIORITIES, SUPPORTED_CURRENCIES
from ..service import CollectionService


def _secret_key() -> str:
    path = home_dir() / ".flask_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    return key


def _template_folder() -> str | None:
    """When bundled by PyInstaller, templates live under the unpack dir
    (``sys._MEIPASS``) rather than next to this module."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "collect", "web", "templates")
    return None  # default: package-relative "templates"


def create_app(service: CollectionService | None = None) -> Flask:
    tf = _template_folder()
    app = Flask(__name__, template_folder=tf) if tf else Flask(__name__)
    app.secret_key = _secret_key()
    svc = service or CollectionService()

    # ---- CSRF (no extra dependency) ------------------------------------------

    @app.before_request
    def _ensure_csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)

    @app.context_processor
    def _inject():
        return {
            "csrf_token": session.get("csrf", ""),
            "supported_currencies": SUPPORTED_CURRENCIES,
            "priorities": PRIORITIES,
            "display_currency": svc.get_display_currency(),
            "show_welcome": not svc.is_onboarded(),
        }

    def csrf_check():
        if request.form.get("csrf") != session.get("csrf"):
            abort(400, "Invalid CSRF token")

    def csrf_protect(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            csrf_check()
            return view(*args, **kwargs)
        return wrapped

    # ---- view helpers ---------------------------------------------------------

    def item_view(item, rates, target):
        converted = currency.convert(item.value_cents, item.currency, target, rates)
        return {
            "id": item.id, "name": item.name, "category": item.category,
            "brand": item.brand, "acquired": item.acquired, "notes": item.notes,
            "image_url": item.image_url, "currency": item.currency,
            "original": currency.format_amount(item.value_cents, item.currency),
            "converted": currency.format_amount(converted, target),
            "converted_cents": converted,
            "same_currency": item.currency == target,
        }

    def wish_view(w, rates, target):
        converted = currency.convert(w.est_value_cents, w.currency, target, rates)
        return {
            "id": w.id, "name": w.name, "category": w.category, "brand": w.brand,
            "priority": w.priority, "source_url": w.source_url, "notes": w.notes,
            "image_url": w.image_url, "currency": w.currency,
            "original": currency.format_amount(w.est_value_cents, w.currency),
            "converted": currency.format_amount(converted, target),
            "same_currency": w.currency == target,
        }

    # ---- My Collection (showcase) --------------------------------------------

    @app.route("/")
    def index():
        target = svc.get_display_currency()
        rates = currency.get_rates()
        views = [item_view(i, rates, target) for i in svc.list_items()]
        by_cat: dict[str, dict] = {}
        for v in views:
            slot = by_cat.setdefault(v["category"], {"count": 0, "cents": 0})
            slot["count"] += 1
            slot["cents"] += v["converted_cents"]
        breakdown = [
            {"category": c, "count": d["count"], "cents": d["cents"],
             "total": currency.format_amount(d["cents"], target)}
            for c, d in sorted(by_cat.items(), key=lambda kv: -kv[1]["cents"])
        ]
        total_cents = sum(v["converted_cents"] for v in views)
        return render_template(
            "my_collection.html", items=views, breakdown=breakdown,
            display_currency=target, rates_label=currency.rates_age_label(rates),
            total=currency.format_amount(total_cents, target),
            total_cents=total_cents, count=len(views),
            missing_images=sum(1 for v in views if not v["image_url"]),
        )

    # ---- Manage Collection ----------------------------------------------------

    @app.route("/manage")
    def manage():
        target = svc.get_display_currency()
        rates = currency.get_rates()
        category = request.args.get("category") or None
        query = request.args.get("q", "").strip()
        items = (svc.search_items(query, category=category) if query
                 else svc.list_items(category=category))
        counts = {c: 0 for c in svc.list_categories()}
        for it in svc.list_items():
            counts[it.category] = counts.get(it.category, 0) + 1
        return render_template(
            "manage.html",
            items=[item_view(i, rates, target) for i in items],
            categories=svc.list_categories(), counts=counts,
            active_category=category, query=query, display_currency=target,
        )

    @app.route("/add", methods=["POST"])
    @csrf_protect
    def add():
        try:
            item = svc.add_item(
                name=request.form.get("name", ""),
                category=request.form.get("category", ""),
                brand=request.form.get("brand", ""),
                acquired=request.form.get("acquired", ""),
                value=float(request.form.get("value") or 0),
                currency=request.form.get("currency", "USD"),
                notes=request.form.get("notes", ""),
                image_url=request.form.get("image_url", ""),
            )
            if not item.image_url:
                svc.suggest_image_for(item.id)
            flash(f"Added {item.name}.", "success")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(request.form.get("next") or url_for("manage"))

    @app.route("/item/<item_id>/edit", methods=["GET", "POST"])
    def edit(item_id):
        try:
            item = svc.get_item(item_id)
        except CollectError:
            abort(404)
        if request.method == "GET":
            return render_template(
                "edit.html",
                item=item_view(item, currency.get_rates(), svc.get_display_currency()),
                raw=item, categories=svc.list_categories(),
            )
        csrf_check()
        try:
            svc.update_item(
                item_id,
                name=request.form.get("name"),
                category=request.form.get("category"),
                brand=request.form.get("brand"),
                acquired=request.form.get("acquired"),
                value=float(request.form.get("value") or 0),
                currency=request.form.get("currency"),
                notes=request.form.get("notes"),
                image_url=request.form.get("image_url"),
            )
            flash("Changes saved.", "success")
        except CollectError as e:
            flash(str(e), "error")
            return redirect(url_for("edit", item_id=item_id))
        return redirect(url_for("manage"))

    @app.route("/item/<item_id>/remove", methods=["POST"])
    @csrf_protect
    def remove(item_id):
        _run(lambda: svc.remove_item(item_id), "Item removed.")
        return redirect(request.form.get("next") or url_for("manage"))

    @app.route("/item/<item_id>/suggest-image", methods=["POST"])
    @csrf_protect
    def suggest_image(item_id):
        try:
            item = svc.suggest_image_for(item_id, overwrite=True)
            ok = bool(item.image_url)
            flash("Image refreshed." if ok else "No image found.",
                  "success" if ok else "error")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(request.form.get("next") or url_for("edit", item_id=item_id))

    @app.route("/images/fetch", methods=["POST"])
    @csrf_protect
    def fetch_images():
        filled = svc.ensure_images()
        flash(f"Fetched {filled} image(s) from the web.", "success")
        return redirect(request.form.get("next") or url_for("index"))

    # ---- categories -----------------------------------------------------------

    @app.route("/categories/add", methods=["POST"])
    @csrf_protect
    def category_add():
        _run(lambda: svc.add_category(request.form.get("name", "")), "Category added.")
        return redirect(url_for("manage"))

    @app.route("/categories/rename", methods=["POST"])
    @csrf_protect
    def category_rename():
        _run(lambda: svc.rename_category(request.form.get("old", ""),
                                         request.form.get("new", "")), "Category renamed.")
        return redirect(url_for("manage"))

    @app.route("/categories/remove", methods=["POST"])
    @csrf_protect
    def category_remove():
        _run(lambda: svc.remove_category(request.form.get("name", ""),
                                         force=request.form.get("force") == "1"),
             "Category removed.")
        return redirect(url_for("manage"))

    # ---- Wishlist -------------------------------------------------------------

    @app.route("/wishlist")
    def wishlist():
        target = svc.get_display_currency()
        rates = currency.get_rates()
        views = [wish_view(w, rates, target) for w in svc.list_wishlist()]
        return render_template(
            "wishlist.html", items=views, categories=svc.list_categories(),
            display_currency=target, count=len(views),
        )

    @app.route("/wishlist/add", methods=["POST"])
    @csrf_protect
    def wishlist_add():
        try:
            w = svc.add_wishlist_item(
                name=request.form.get("name", ""),
                category=request.form.get("category", ""),
                brand=request.form.get("brand", ""),
                est_value=float(request.form.get("est_value") or 0),
                currency=request.form.get("currency", "USD"),
                priority=request.form.get("priority", "Medium"),
                source_url=request.form.get("source_url", ""),
                notes=request.form.get("notes", ""),
                image_url=request.form.get("image_url", ""),
            )
            if not w.image_url:
                svc.suggest_wishlist_image(w.id)
            flash(f"Added {w.name} to wishlist.", "success")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(url_for("wishlist"))

    @app.route("/wishlist/<item_id>/remove", methods=["POST"])
    @csrf_protect
    def wishlist_remove(item_id):
        _run(lambda: svc.remove_wishlist_item(item_id), "Removed from wishlist.")
        return redirect(url_for("wishlist"))

    @app.route("/wishlist/<item_id>/promote", methods=["POST"])
    @csrf_protect
    def wishlist_promote(item_id):
        try:
            val = request.form.get("value")
            item = svc.promote_wishlist_item(
                item_id,
                acquired=request.form.get("acquired", ""),
                value=float(val) if val else None,
            )
            flash(f"Moved {item.name} into your collection.", "success")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(url_for("wishlist"))

    @app.route("/wishlist/<item_id>/suggest-image", methods=["POST"])
    @csrf_protect
    def wishlist_suggest_image(item_id):
        _run(lambda: svc.suggest_wishlist_image(item_id, overwrite=True),
             "Image refreshed.")
        return redirect(url_for("wishlist"))

    # ---- currency -------------------------------------------------------------

    @app.route("/currency", methods=["POST"])
    @csrf_protect
    def set_currency():
        _run(lambda: svc.set_display_currency(request.form.get("currency", "")), None)
        return redirect(request.form.get("next") or url_for("index"))

    # ---- onboarding / help ----------------------------------------------------

    @app.route("/help")
    def help_page():
        return render_template("help.html")

    @app.route("/onboard/dismiss", methods=["POST"])
    @csrf_protect
    def onboard_dismiss():
        svc.mark_onboarded(True)
        return redirect(request.form.get("next") or url_for("index"))

    @app.route("/samples", methods=["POST"])
    @csrf_protect
    def load_samples():
        n = svc.load_sample_data()
        svc.mark_onboarded(True)
        flash(f"Loaded {n} sample piece(s) to explore. Clear them anytime "
              "from the Manage tab." if n else
              "Sample data is only added to an empty collection.", "success")
        return redirect(url_for("index"))

    @app.route("/reset", methods=["POST"])
    @csrf_protect
    def reset():
        svc.clear_all()
        flash("All items and wishlist entries removed.", "success")
        return redirect(url_for("index"))

    def _run(action, success_msg):
        try:
            action()
            if success_msg:
                flash(success_msg, "success")
        except CollectError as e:
            flash(str(e), "error")

    return app


def main() -> None:
    app = create_app()
    host = os.environ.get("COLLECT_HOST", "127.0.0.1")
    port = int(os.environ.get("COLLECT_PORT", "5000"))
    app.run(host=host, port=port, debug=os.environ.get("COLLECT_DEBUG") == "1")


if __name__ == "__main__":
    main()
