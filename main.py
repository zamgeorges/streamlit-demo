# app.py — Streamlit E‑commerce demo (stable, single‑file)
# -------------------------------------------------------
# Features
# - Catalog with search, filters, sort, and pagination
# - Product cards with images, ratings, and "Add to cart"
# - Cart in sidebar with quantity editing, remove, and clear
# - Checkout mock flow + order receipt
# - Cached in‑memory dataset; easy to swap with your own CSV/API
# - Robust state management and defensive guards to avoid crashes
# - Export cart to CSV / JSON; import cart from JSON
# - Responsive layout (mobile/desktop) using Streamlit columns
# - Minimal dependencies: streamlit + pandas + numpy (optional)

from __future__ import annotations
import json
import math
import textwrap
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

# ---------- Page config ----------
st.set_page_config(
    page_title="ShopLite — Demo e‑commerce",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Utilities ----------
CURRENCY = "€"

@st.cache_data(show_spinner=False)
def load_products() -> pd.DataFrame:
    """Load a demo catalog. Replace with your own CSV/API.

    Returns a normalized DataFrame with columns:
    id, title, description, price, category, rating, stock, image
    """
    data = [
        {
            "id": i,
            "title": f"Produit {i:02d}",
            "description": textwrap.shorten(
                "Un super produit de démonstration, idéal pour montrer Streamlit en e‑commerce. "
                "Compatible livraison rapide et satisfait ou remboursé.",
                width=160,
                placeholder="…",
            ),
            "price": round(4.99 + (i * 1.75) % 65, 2),
            "category": ["Maison", "Sport", "Tech", "Mode", "Beauté"][i % 5],
            "rating": round(3.2 + ((i * 37) % 18) / 10, 1),  # 3.2 → 4.9
            "stock": int(3 + (i * 7) % 30),
            "image": f"https://picsum.photos/seed/prod{i}/600/400",
        }
        for i in range(1, 61)
    ]
    df = pd.DataFrame(data)
    # Clip rating to 5.0
    df["rating"] = df["rating"].clip(0, 5)
    return df


def money(x: float) -> str:
    return f"{x:,.2f} {CURRENCY}".replace(",", " ")


def init_state():
    ss = st.session_state
    ss.setdefault("cart", {})  # id -> {qty, price, title}
    ss.setdefault("orders", []) # list of receipts
    ss.setdefault("import_err", None)


@dataclass
class CartItem:
    id: int
    title: str
    price: float
    qty: int

    @property
    def subtotal(self) -> float:
        return self.price * self.qty


# ---------- Catalog UI ----------

def render_product_card(row: pd.Series, key: str):
    col_img, col_txt = st.columns([1, 1.4], vertical_alignment="center")
    with col_img:
        try:
            st.image(row.image, use_column_width=True)
        except Exception:
            st.image(
                "https://via.placeholder.com/600x400.png?text=Image+indisponible",
                use_column_width=True,
            )
    with col_txt:
        st.subheader(row.title)
        st.caption(f"Catégorie · {row.category} · ⭐ {row.rating}")
        st.write(row.description)
        st.markdown(f"**{money(row.price)}**")

        col_qty, col_btn = st.columns([1, 2])
        with col_qty:
            qty = st.number_input(
                "Qté",
                min_value=1,
                max_value=int(row.stock) if row.stock > 0 else 1,
                value=1,
                step=1,
                key=f"qty_{key}_{row.id}",
                help="Quantité à ajouter au panier",
            )
        with col_btn:
            disabled = row.stock <= 0
            if st.button(
                "➕ Ajouter au panier",
                key=f"add_{key}_{row.id}",
                type="primary",
                disabled=disabled,
            ):
                add_to_cart(row, int(qty))
                st.toast(f"Ajouté: {row.title} × {qty}")
        if row.stock <= 0:
            st.error("Rupture de stock")
        elif row.stock < 5:
            st.warning(f"Stock faible: {row.stock}")


def add_to_cart(row: pd.Series, qty: int):
    cart: Dict[int, Dict] = st.session_state.cart
    if qty <= 0:
        return
    if row.id in cart:
        cart[row.id]["qty"] += qty
    else:
        cart[row.id] = {"title": row.title, "price": float(row.price), "qty": int(qty)}


def remove_from_cart(pid: int):
    st.session_state.cart.pop(pid, None)


def update_qty(pid: int, qty: int):
    if qty <= 0:
        remove_from_cart(pid)
    else:
        st.session_state.cart[pid]["qty"] = int(qty)


def cart_totals(df: pd.DataFrame):
    cart = st.session_state.cart
    total = 0.0
    n_items = 0
    for pid, item in cart.items():
        total += item["price"] * item["qty"]
        n_items += item["qty"]
    shipping = 0.0 if total >= 50 else 4.99 if total > 0 else 0.0
    tax = round(total * 0.2, 2)  # TVA 20% (démo)
    grand = round(total + shipping + tax, 2)
    return {
        "n_items": n_items,
        "subtotal": round(total, 2),
        "shipping": shipping,
        "tax": tax,
        "grand": grand,
    }


def export_cart(fmt: str) -> Optional[str]:
    cart = st.session_state.cart
    if not cart:
        return None
    rows = []
    for pid, item in cart.items():
        rows.append({
            "id": pid,
            "title": item["title"],
            "price": item["price"],
            "qty": item["qty"],
            "subtotal": round(item["price"] * item["qty"], 2),
        })
    df = pd.DataFrame(rows)
    if fmt == "csv":
        path = "cart.csv"
        df.to_csv(path, index=False)
        return path
    elif fmt == "json":
        path = "cart.json"
        df.to_json(path, orient="records", force_ascii=False)
        return path
    return None


def import_cart(file):
    try:
        data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Format inattendu (JSON doit être une liste d'articles)")
        new_cart = {}
        for entry in data:
            pid = int(entry.get("id"))
            title = str(entry.get("title"))
            price = float(entry.get("price"))
            qty = int(entry.get("qty", 1))
            if qty > 0:
                new_cart[pid] = {"title": title, "price": price, "qty": qty}
        st.session_state.cart = new_cart
        st.session_state.import_err = None
        st.toast("Panier importé")
    except Exception as e:
        st.session_state.import_err = str(e)


# ---------- Sidebar (Cart) ----------

def sidebar_cart(df: pd.DataFrame):
    with st.sidebar:
        st.header("🛒 Panier")
        cart = st.session_state.cart
        if not cart:
            st.info("Votre panier est vide.")
        else:
            for pid, item in list(cart.items()):
                with st.container(border=True):
                    st.markdown(f"**{item['title']}**")
                    col_q, col_p, col_r = st.columns([1, 1, 1])
                    with col_q:
                        new_q = st.number_input(
                            "Qté",
                            min_value=0,
                            max_value=999,
                            value=int(item["qty"]),
                            step=1,
                            key=f"cart_qty_{pid}",
                        )
                        if new_q != item["qty"]:
                            update_qty(pid, int(new_q))
                    with col_p:
                        st.caption("Prix")
                        st.write(money(item["price"]))
                    with col_r:
                        if st.button("Retirer", key=f"rm_{pid}"):
                            remove_from_cart(pid)
                            st.rerun()
            st.divider()
            totals = cart_totals(df)
            st.metric("Articles", totals["n_items"])
            st.text(f"Sous‑total: {money(totals['subtotal'])}")
            st.text(f"Livraison: {money(totals['shipping'])}")
            st.text(f"TVA (20%): {money(totals['tax'])}")
            st.markdown(f"### Total: {money(totals['grand'])}")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🧹 Vider le panier"):
                    st.session_state.cart = {}
                    st.rerun()
            with col_b:
                st.download_button(
                    "💾 Export CSV",
                    data=open(export_cart("csv"), "rb").read() if cart else b"",
                    file_name="panier.csv",
                    mime="text/csv",
                    disabled=not bool(cart),
                )

            st.download_button(
                "💾 Export JSON",
                data=open(export_cart("json"), "rb").read() if cart else b"",
                file_name="panier.json",
                mime="application/json",
                disabled=not bool(cart),
            )

            st.caption("Importer un panier (JSON)")
            file = st.file_uploader("panier.json", type=["json"], key="uploader_json")
            if file is not None:
                import_cart(file)
                if st.session_state.import_err:
                    st.error(st.session_state.import_err)

            st.divider()
            st.markdown("#### Paiement (démo)")
            name = st.text_input("Nom complet")
            email = st.text_input("Email")
            address = st.text_area("Adresse de livraison")
            agree = st.checkbox("J'accepte les conditions")
            can_pay = bool(cart) and name and email and address and agree
            if st.button("✅ Payer maintenant", type="primary", disabled=not can_pay):
                receipt = {
                    "ts": datetime.utcnow().isoformat(),
                    "name": name,
                    "email": email,
                    "address": address,
                    "items": [
                        {"id": pid, **item} for pid, item in st.session_state.cart.items()
                    ],
                    "totals": cart_totals(df),
                    "order_id": f"ORD-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                }
                st.session_state.orders.append(receipt)
                st.session_state.cart = {}
                st.success("Paiement simulé — commande confirmée !")
                st.balloons()


# ---------- Filters & Catalog listing ----------

def catalog_view(df: pd.DataFrame):
    st.title("🛍️ ShopLite — E‑commerce (démo)")
    st.caption("Streamlit full‑power, version stable et minimalement dépendante.")

    with st.container(border=True):
        col_s, col_cat, col_pr, col_rt, col_sort = st.columns([2, 1, 2, 1, 1])
        with col_s:
            q = st.text_input("Recherche", placeholder="Tapez un nom de produit…")
        with col_cat:
            cats = sorted(df["category"].unique())
            cat = st.multiselect("Catégorie", options=cats, default=[])
        with col_pr:
            pmin, pmax = float(df.price.min()), float(df.price.max())
            price = st.slider("Prix", min_value=0.0, max_value=max(100.0, pmax), value=(0.0, max(50.0, pmax/1.2)), step=0.5)
        with col_rt:
            rating = st.slider("Note mini", min_value=0.0, max_value=5.0, value=3.0, step=0.1)
        with col_sort:
            sort = st.selectbox("Tri", ["Pertinence", "Prix ↑", "Prix ↓", "Note ↓", "Stock ↓"]) 

    # Filtering
    out = df.copy()
    if q:
        ql = q.lower()
        out = out[out["title"].str.lower().str.contains(ql) | out["description"].str.lower().str.contains(ql)]
    if cat:
        out = out[out["category"].isin(cat)]
    out = out[(out.price >= price[0]) & (out.price <= price[1])]
    out = out[out.rating >= rating]

    # Sorting
    if sort == "Prix ↑":
        out = out.sort_values("price", ascending=True)
    elif sort == "Prix ↓":
        out = out.sort_values("price", ascending=False)
    elif sort == "Note ↓":
        out = out.sort_values("rating", ascending=False)
    elif sort == "Stock ↓":
        out = out.sort_values("stock", ascending=False)

    # Pagination
    per_page = st.select_slider("Produits par page", [6, 9, 12, 15, 18, 24], value=12)
    total = len(out)
    pages = max(1, math.ceil(total / per_page))
    page = st.number_input("Page", min_value=1, max_value=pages, step=1, value=1)
    start, end = (page - 1) * per_page, page * per_page

    st.caption(f"{total} produit(s) — page {page}/{pages}")

    # Grid render
    grid = out.iloc[start:end]
    # Display as 3‑column cards on desktop, 1‑2 on narrow using columns
    n_cols = 3 if st.viewport().width and st.viewport().width > 1000 else 2
    if n_cols < 1:
        n_cols = 1
    cols = st.columns(n_cols)

    for i, (_, row) in enumerate(grid.iterrows()):
        with cols[i % n_cols]:
            with st.container(border=True):
                render_product_card(row, key=f"list{page}")


# ---------- Orders (mock history) ----------

def orders_view():
    st.title("📦 Mes commandes (démo)")
    orders = st.session_state.orders
    if not orders:
        st.info("Vous n'avez pas encore de commandes.")
        return
    for order in reversed(orders):
        with st.expander(f"{order['order_id']} — {order['ts']}"):
            st.write(f"**Client:** {order['name']}  ")
            st.write(f"**Email:** {order['email']}  ")
            st.write(f"**Adresse:** {order['address']}")
            st.write("**Articles**")
            df = pd.DataFrame(order["items"])
            df["subtotal"] = df["price"] * df["qty"]
            st.dataframe(df[["id", "title", "price", "qty", "subtotal"]], hide_index=True, use_container_width=True)
            t = order["totals"]
            st.write(
                f"Sous‑total: {money(t['subtotal'])} | Livraison: {money(t['shipping'])} | TVA: {money(t['tax'])} | **Total: {money(t['grand'])}**"
            )


# ---------- Main ----------

def main():
    init_state()
    df = load_products()

    # Sidebar cart (persists across tabs)
    sidebar_cart(df)

    # Tabs for main content
    tab1, tab2 = st.tabs(["🛒 Catalogue", "📦 Commandes"])
    with tab1:
        catalog_view(df)
    with tab2:
        orders_view()


if __name__ == "__main__":
    main()
