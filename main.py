# app.py — Mini e-commerce Streamlit (texte only, <200 lignes)
from __future__ import annotations
import math, textwrap
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="ShopLite (texte)", page_icon="🛍️", layout="wide")

# ---------------------- Données démo ----------------------
PRODUCTS = [
    {"id": i, "title": f"Produit {i:02d}",
     "desc": textwrap.shorten(
         "Produit démo, livraison rapide, satisfait ou remboursé. Parfait pour tester Streamlit.",
         width=120, placeholder="…"),
     "price": round(4.99 + (i * 1.75) % 60, 2),
     "cat": ["Maison", "Sport", "Tech", "Mode", "Beauté"][i % 5],
     "rating": round(3.2 + ((i * 37) % 18) / 10, 1),
     "stock": int(3 + (i * 7) % 30)}
    for i in range(1, 51)
]

# ---------------------- Utils / State ----------------------
def money(x: float) -> str: return f"{x:,.2f} €".replace(",", " ")
def init_state():
    st.session_state.setdefault("cart", {})   # id -> {"title","price","qty"}
    st.session_state.setdefault("orders", []) # reçus

def add_to_cart(p: dict, qty: int):
    if qty <= 0: return
    c = st.session_state.cart
    item = c.get(p["id"], {"title": p["title"], "price": p["price"], "qty": 0})
    item["qty"] += qty
    c[p["id"]] = item

def update_qty(pid: int, qty: int):
    c = st.session_state.cart
    if qty <= 0: c.pop(pid, None)
    else:
        if pid in c: c[pid]["qty"] = int(qty)

def cart_totals():
    c = st.session_state.cart
    subtotal = sum(v["price"] * v["qty"] for v in c.values())
    shipping = 0.0 if subtotal >= 50 else (4.99 if subtotal > 0 else 0.0)
    tax = round(subtotal * 0.2, 2)   # TVA 20% (démo)
    grand = round(subtotal + shipping + tax, 2)
    n_items = sum(v["qty"] for v in c.values())
    return {"n": n_items, "sub": round(subtotal, 2), "ship": shipping, "tax": tax, "total": grand}

# ---------------------- Sidebar Panier ----------------------
def sidebar_cart():
    with st.sidebar:
        st.header("🛒 Panier")
        c = st.session_state.cart
        if not c:
            st.info("Panier vide.")
        else:
            for pid, item in list(c.items()):
                with st.container(border=True):
                    st.markdown(f"**{item['title']}** — {money(item['price'])}")
                    col1, col2 = st.columns([1,1])
                    with col1:
                        q = st.number_input("Qté", 0, 999, item["qty"], 1, key=f"cart_{pid}")
                        if q != item["qty"]:
                            update_qty(pid, q)
                    with col2:
                        if st.button("Retirer", key=f"rm_{pid}"):
                            update_qty(pid, 0)
                            st.rerun()
            st.divider()
            t = cart_totals()
            st.metric("Articles", t["n"])
            st.text(f"Sous-total: {money(t['sub'])}")
            st.text(f"Livraison: {money(t['ship'])}")
            st.text(f"TVA (20%): {money(t['tax'])}")
            st.markdown(f"**Total: {money(t['total'])}**")
            colA, colB = st.columns(2)
            with colA:
                if st.button("🧹 Vider le panier"):
                    st.session_state.cart = {}
                    st.rerun()
            with colB:
                pass
            st.subheader("Paiement (démo)")
            name = st.text_input("Nom complet")
            email = st.text_input("Email")
            addr = st.text_area("Adresse de livraison")
            agree = st.checkbox("J’accepte les conditions")
            can_pay = bool(c) and name and email and addr and agree
            if st.button("✅ Payer maintenant", disabled=not can_pay, type="primary"):
                receipt = {
                    "id": f"ORD-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                    "ts": datetime.utcnow().isoformat(),
                    "name": name, "email": email, "addr": addr,
                    "items": [{**v, "id": k} for k, v in c.items()],
                    "totals": cart_totals()
                }
                st.session_state.orders.append(receipt)
                st.session_state.cart = {}
                st.success("Paiement simulé — commande confirmée !")

# ---------------------- Catalogue ----------------------
def catalog(products: list[dict]):
    st.title("🛍️ ShopLite — Catalogue (texte)")
    # Filtres
    colA, colB, colC, colD = st.columns([2,1,2,1])
    with colA:
        q = st.text_input("Recherche", placeholder="Nom / description…")
    with colB:
        cats = sorted({p["cat"] for p in products})
        cat = st.multiselect("Catégories", cats)
    with colC:
        pmin = min(p["price"] for p in products)
        pmax = max(p["price"] for p in products)
        p_range = st.slider("Prix", 0.0, max(100.0, float(pmax)), (0.0, float(pmax)), 0.5)
    with colD:
        sort = st.selectbox("Tri", ["Pertinence","Prix ↑","Prix ↓","Note ↓","Stock ↓"])

    # Filtrage
    out = products
    if q:
        ql = q.lower()
        out = [p for p in out if ql in p["title"].lower() or ql in p["desc"].lower()]
    if cat:
        out = [p for p in out if p["cat"] in cat]
    out = [p for p in out if p["price"] >= p_range[0] and p["price"] <= p_range[1]]
    out = [p for p in out if p["rating"] >= 0]  # placeholder pour future note mini si besoin

    # Tri
    if sort == "Prix ↑":   out = sorted(out, key=lambda x: x["price"])
    elif sort == "Prix ↓": out = sorted(out, key=lambda x: -x["price"])
    elif sort == "Note ↓": out = sorted(out, key=lambda x: -x["rating"])
    elif sort == "Stock ↓":out = sorted(out, key=lambda x: -x["stock"])

    # Pagination
    per_page = st.select_slider("Produits par page", [6,9,12,15,18,24], value=12)
    total = len(out); pages = max(1, math.ceil(total/per_page))
    page = st.number_input("Page", 1, pages, 1)
    st.caption(f"{total} produit(s) — page {page}/{pages}")
    grid = out[(page-1)*per_page : page*per_page]

    # Rendu liste (texte)
    for p in grid:
        with st.container(border=True):
            st.markdown(f"**{p['title']}** — {money(p['price'])}")
            st.caption(f"Catégorie: {p['cat']} · ⭐ {p['rating']} · Stock: {p['stock']}")
            st.write(p["desc"])
            c1, c2, c3 = st.columns([1,1,2])
            with c1:
                qty = st.number_input("Qté", 1, max(1, p["stock"]), 1, 1, key=f"qty_{p['id']}")
            with c2:
                disabled = p["stock"] <= 0
                if st.button("Ajouter", key=f"add_{p['id']}", disabled=disabled):
                    add_to_cart(p, int(qty))
                    st.toast(f"Ajouté: {p['title']} × {qty}")
            with c3:
                st.markdown("")

# ---------------------- Commandes ----------------------
def orders_view():
    st.title("📦 Mes commandes (démo)")
    orders = st.session_state.orders
    if not orders:
        st.info("Aucune commande.")
        return
    for o in reversed(orders):
        with st.expander(f"{o['id']} — {o['ts']}"):
            st.write(f"**Client:** {o['name']}  \n**Email:** {o['email']}  \n**Adresse:** {o['addr']}")
            st.write("**Articles:**")
            for it in o["items"]:
                st.write(f"- {it['title']} × {it['qty']} — {money(it['price']*it['qty'])}")
            t = o["totals"]
            st.write(f"Sous-total {money(t['sub'])} | Livraison {money(t['ship'])} | TVA {money(t['tax'])} | **Total {money(t['total'])}**")

# ---------------------- Main ----------------------
def main():
    init_state()
    sidebar_cart()
    tab1, tab2 = st.tabs(["🛒 Catalogue", "📦 Commandes"])
    with tab1: catalog(PRODUCTS)
    with tab2: orders_view()

if __name__ == "__main__":
    main()
