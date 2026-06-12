from flask import Flask, redirect, render_template, request, url_for

from . import commands

app = Flask(__name__)


@app.route("/")
def index():
    category = request.args.get("category") or None
    query = request.args.get("q", "").strip()

    if query:
        items = commands.search_items(query)
        if category:
            items = [i for i in items if i["category"] == category]
    else:
        items = commands.list_items(category=category)

    total_value = sum(float(i.get("value", 0) or 0) for i in items)
    return render_template(
        "index.html",
        items=items,
        categories=sorted(commands.CATEGORIES),
        active_category=category,
        query=query,
        total_value=total_value,
    )


@app.route("/add", methods=["POST"])
def add():
    error = None
    try:
        commands.add_item(
            name=request.form["name"].strip(),
            category=request.form["category"],
            brand=request.form["brand"].strip(),
            acquired=request.form["acquired"].strip(),
            value=float(request.form.get("value") or 0),
            notes=request.form.get("notes", "").strip(),
        )
    except (ValueError, KeyError) as e:
        error = str(e)

    if error:
        return render_template(
            "index.html",
            items=commands.list_items(),
            categories=sorted(commands.CATEGORIES),
            active_category=None,
            query="",
            total_value=sum(
                float(i.get("value", 0) or 0) for i in commands.list_items()
            ),
            error=error,
        ), 400
    return redirect(url_for("index"))


@app.route("/remove", methods=["POST"])
def remove():
    commands.remove_item(request.form["name"])
    return redirect(url_for("index"))


def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
