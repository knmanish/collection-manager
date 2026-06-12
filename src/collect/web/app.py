"""Flask adapter over the service layer.

Thin: every route parses the request, calls the service, and renders. No
business logic lives here. Hardened for local use with a persisted secret key,
a lightweight per-session CSRF token on every POST, and flash messaging.
"""

from __future__ import annotations

import secrets
from functools import wraps

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for,
)

from .. import currency
from ..config import home_dir
from ..errors import CollectError
from ..model import SUPPORTED_CURRENCIES
from ..service import CollectionService


def _secret_key() -> str:
    path = home_dir() / ".flask_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    return key


def create_app(service: CollectionService | None = None) -> Flask:
    app = Flask(__name__)
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
        }

    def csrf_protect(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.form.get("csrf") != session.get("csrf"):
                abort(400, "Invalid CSRF token")
            return view(*args, **kwargs)
        return wrapped

    # ---- view helpers ---------------------------------------------------------

    def display_currency() -> str:
        return svc.get_display_currency()

    def item_view(item, rates, target):
        converted = currency.convert(item.value_cents, item.currency, target, rates)
        return {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "brand": item.brand,
            "acquired": item.acquired,
            "notes": item.notes,
            "image_url": item.image_url,
            "currency": item.currency,
            "original": currency.format_amount(item.value_cents, item.currency),
            "converted": currency.format_amount(converted, target),
            "converted_cents": converted,
            "same_currency": item.currency == target,
        }

    # ---- routes: collection ---------------------------------------------------

    @app.route("/")
    def index():
        target = display_currency()
        rates = currency.get_rates()
        category = request.args.get("category") or None
        query = request.args.get("q", "").strip()
        items = (
            svc.search_items(query, category=category)
            if query else svc.list_items(category=category)
        )
        views = [item_view(i, rates, target) for i in items]
        total = sum(v["converted_cents"] for v in views)
        return render_template(
            "index.html",
            items=views,
            categories=svc.list_categories(),
            active_category=category,
            query=query,
            display_currency=target,
            rates_label=currency.rates_age_label(rates),
            total=currency.format_amount(total, target),
            count=len(views),
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
                svc.suggest_image_for(item.id)  # best-effort auto image
            flash(f"Added {item.name}.", "success")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(request.form.get("next") or url_for("index"))

    @app.route("/item/<item_id>/edit", methods=["GET", "POST"])
    def edit(item_id):
        try:
            item = svc.get_item(item_id)
        except CollectError:
            abort(404)
        if request.method == "GET":
            return render_template(
                "edit.html",
                item=item_view(item, currency.get_rates(), display_currency()),
                raw=item,
                categories=svc.list_categories(),
            )
        if request.form.get("csrf") != session.get("csrf"):
            abort(400, "Invalid CSRF token")
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
        return redirect(url_for("index"))

    @app.route("/item/<item_id>/remove", methods=["POST"])
    @csrf_protect
    def remove(item_id):
        try:
            svc.remove_item(item_id)
            flash("Item removed.", "success")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(request.form.get("next") or url_for("index"))

    @app.route("/item/<item_id>/suggest-image", methods=["POST"])
    @csrf_protect
    def suggest_image(item_id):
        try:
            item = svc.suggest_image_for(item_id, overwrite=True)
            flash("Image refreshed." if item.image_url else "No image found.",
                  "success" if item.image_url else "error")
        except CollectError as e:
            flash(str(e), "error")
        return redirect(request.form.get("next") or url_for("edit", item_id=item_id))

    # ---- routes: categories ---------------------------------------------------

    @app.route("/categories")
    def categories():
        counts = {c: 0 for c in svc.list_categories()}
        for it in svc.list_items():
            counts[it.category] = counts.get(it.category, 0) + 1
        return render_template("categories.html", counts=counts)

    @app.route("/categories/add", methods=["POST"])
    @csrf_protect
    def category_add():
        _run(lambda: svc.add_category(request.form.get("name", "")),
             "Category added.")
        return redirect(url_for("categories"))

    @app.route("/categories/rename", methods=["POST"])
    @csrf_protect
    def category_rename():
        _run(lambda: svc.rename_category(
            request.form.get("old", ""), request.form.get("new", "")),
            "Category renamed.")
        return redirect(url_for("categories"))

    @app.route("/categories/remove", methods=["POST"])
    @csrf_protect
    def category_remove():
        _run(lambda: svc.remove_category(
            request.form.get("name", ""),
            force=request.form.get("force") == "1"),
            "Category removed.")
        return redirect(url_for("categories"))

    # ---- routes: summary + currency ------------------------------------------

    @app.route("/summary")
    def summary():
        target = display_currency()
        rates = currency.get_rates()
        items = svc.list_items()
        views = [item_view(i, rates, target) for i in items]
        by_cat: dict[str, dict] = {}
        for v in views:
            slot = by_cat.setdefault(v["category"], {"count": 0, "cents": 0})
            slot["count"] += 1
            slot["cents"] += v["converted_cents"]
        breakdown = [
            {
                "category": cat,
                "count": d["count"],
                "total": currency.format_amount(d["cents"], target),
                "cents": d["cents"],
            }
            for cat, d in sorted(by_cat.items(), key=lambda kv: -kv[1]["cents"])
        ]
        total_cents = sum(v["converted_cents"] for v in views)
        missing_images = sum(1 for v in views if not v["image_url"])
        return render_template(
            "summary.html",
            items=views,
            breakdown=breakdown,
            categories=svc.list_categories(),
            display_currency=target,
            rates_label=currency.rates_age_label(rates),
            total=currency.format_amount(total_cents, target),
            total_cents=total_cents,
            count=len(views),
            missing_images=missing_images,
        )

    @app.route("/currency", methods=["POST"])
    @csrf_protect
    def set_currency():
        _run(lambda: svc.set_display_currency(request.form.get("currency", "")),
             None)
        return redirect(request.form.get("next") or url_for("index"))

    @app.route("/images/fetch", methods=["POST"])
    @csrf_protect
    def fetch_images():
        filled = svc.ensure_images()
        flash(f"Fetched {filled} image(s) from the web.", "success")
        return redirect(request.form.get("next") or url_for("summary"))

    def _run(action, success_msg):
        try:
            action()
            if success_msg:
                flash(success_msg, "success")
        except CollectError as e:
            flash(str(e), "error")

    return app


def main() -> None:
    import os
    app = create_app()
    debug = os.environ.get("COLLECT_DEBUG") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug)


if __name__ == "__main__":
    main()
