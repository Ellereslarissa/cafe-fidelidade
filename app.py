
import math
import sqlite3
from datetime import datetime
import streamlit as st

DB_PATH = "data.db"

# -------------------------
# Database helpers
# -------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE,
        email TEXT,
        stamps INTEGER DEFAULT 0,
        total_purchases REAL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        amount REAL DEFAULT 0,
        stamps_added INTEGER DEFAULT 0,
        type TEXT NOT NULL CHECK (type IN ('purchase', 'redeem', 'adjust')),
        note TEXT,
        ts TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    # defaults
    cur.execute("INSERT OR IGNORE INTO config(key, value) VALUES('stamps_needed', '10');")
    cur.execute("INSERT OR IGNORE INTO config(key, value) VALUES('reais_per_stamp', '10');")
    conn.commit()
    conn.close()

def get_config():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config;")
    data = dict(cur.fetchall())
    conn.close()
    # cast
    data["stamps_needed"] = int(data.get("stamps_needed", "10"))
    data["reais_per_stamp"] = float(data.get("reais_per_stamp", "10"))
    return data

def set_config(stamps_needed: int, reais_per_stamp: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("REPLACE INTO config(key, value) VALUES('stamps_needed', ?)", (str(int(stamps_needed)),))
    cur.execute("REPLACE INTO config(key, value) VALUES('reais_per_stamp', ?)", (str(float(reais_per_stamp)),))
    conn.commit()
    conn.close()

def upsert_customer(name, phone=None, email=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cur.execute("""
            INSERT INTO customers(name, phone, email, created_at)
            VALUES(?, ?, ?, ?);
        """, (name.strip(), (phone or None), (email or None), now))
        conn.commit()
    except sqlite3.IntegrityError:
        # phone already exists -> update name/email
        cur.execute("""
            UPDATE customers SET name = COALESCE(?, name), email = COALESCE(?, email)
            WHERE phone = ?;
        """, (name.strip() or None, email or None, phone))
        conn.commit()
    finally:
        conn.close()

def find_customer_by_phone(phone):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, email, stamps, total_purchases, created_at FROM customers WHERE phone = ?;", (phone,))
    row = cur.fetchone()
    conn.close()
    return row

def find_customer_by_name_like(q):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, email, stamps, total_purchases, created_at FROM customers WHERE name LIKE ? ORDER BY name LIMIT 50;", (f"%{q}%",))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_purchase(customer_id: int, amount: float):
    cfg = get_config()
    reais_per_stamp = cfg["reais_per_stamp"]
    stamps_to_add = int(math.floor(amount / reais_per_stamp)) if reais_per_stamp > 0 else 0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE customers SET stamps = stamps + ?, total_purchases = total_purchases + ? WHERE id = ?;",
                (stamps_to_add, float(amount), int(customer_id)))
    cur.execute("""
        INSERT INTO transactions(customer_id, amount, stamps_added, type, note, ts)
        VALUES(?, ?, ?, 'purchase', NULL, ?);
    """, (int(customer_id), float(amount), int(stamps_to_add), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return stamps_to_add

def redeem_reward(customer_id: int):
    cfg = get_config()
    need = cfg["stamps_needed"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT stamps FROM customers WHERE id = ?;", (int(customer_id),))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Cliente não encontrado."
    current = row[0]
    if current < need:
        conn.close()
        return False, f"Cliente possui apenas {current} carimbos (precisa de {need})."

    cur.execute("UPDATE customers SET stamps = stamps - ? WHERE id = ?;", (need, int(customer_id)))
    cur.execute("""
        INSERT INTO transactions(customer_id, amount, stamps_added, type, note, ts)
        VALUES(?, 0, ?, 'redeem', 'Prêmio resgatado', ?);
    """, (int(customer_id), -need, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return True, "Prêmio resgatado com sucesso!"

def list_customers(limit=200):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, email, stamps, total_purchases, created_at FROM customers ORDER BY created_at DESC LIMIT ?;", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(stamps), SUM(total_purchases) FROM customers;")
    total_customers, total_stamps, total_revenue = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM transactions WHERE type = 'redeem';")
    rewards = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM transactions WHERE type = 'purchase';")
    purchases = cur.fetchone()[0]
    conn.close()
    return {
        "total_customers": total_customers or 0,
        "total_stamps": total_stamps or 0,
        "total_revenue": total_revenue or 0.0,
        "rewards": rewards or 0,
        "purchases": purchases or 0
    }

# -------------------------
# UI helpers
# -------------------------

def loyalty_card(stamps: int, needed: int):
    filled = min(stamps, needed)
    empty = max(needed - filled, 0)
    # Use emojis for a clean stamp visual
    return " ".join(["☕"] * filled + ["○"] * empty)

def header():
    st.markdown("<h1 style='margin-bottom:0'>☕ Cartão Fidelidade - Cafeteria</h1>", unsafe_allow_html=True)
    st.caption("Ganhe carimbos a cada compra e troque por prêmios!")

def nav():
    return st.sidebar.radio("Navegação", ["Registrar Cliente", "Nova Compra", "Resgatar Prêmio", "Buscar Cliente", "Clientes", "Admin"], index=0)

# -------------------------
# Pages
# -------------------------

def page_register():
    st.subheader("Registrar novo cliente")
    with st.form("register_form"):
        name = st.text_input("Nome completo *")
        phone = st.text_input("Telefone (WhatsApp)")
        email = st.text_input("E-mail")
        submitted = st.form_submit_button("Salvar")
    if submitted:
        if not name.strip():
            st.error("Informe o nome.")
        else:
            upsert_customer(name=name, phone=phone.strip() or None, email=email.strip() or None)
            st.success("Cliente registrado/atualizado com sucesso!")

def page_purchase():
    st.subheader("Nova compra")
    phone = st.text_input("Telefone do cliente (para localizar)")
    if phone:
        c = find_customer_by_phone(phone.strip())
        if c:
            cid, name, phone, email, stamps, total, created = c
            cfg = get_config()
            st.info(f"Cliente: **{name}** | Carimbos: **{stamps}** | Necessários p/ prêmio: **{cfg['stamps_needed']}**")
            st.write("Cartão:", loyalty_card(stamps, cfg["stamps_needed"]))
            amount = st.number_input(f"Valor da compra (R$) — 1 carimbo a cada R$ {cfg['reais_per_stamp']}", min_value=0.0, step=1.0, format="%.2f")
            if st.button("Registrar compra"):
                added = add_purchase(cid, amount)
                st.success(f"Compra registrada. Carimbos adicionados: {added}.")
        else:
            st.warning("Cliente não encontrado. Cadastre primeiro na aba 'Registrar Cliente'.")

def page_redeem():
    st.subheader("Resgatar prêmio")
    phone = st.text_input("Telefone do cliente")
    if phone:
        c = find_customer_by_phone(phone.strip())
        if c:
            cid, name, phone, email, stamps, total, created = c
            cfg = get_config()
            st.info(f"Cliente: **{name}** | Carimbos: **{stamps}** | Necessários p/ prêmio: **{cfg['stamps_needed']}**")
            st.write("Cartão:", loyalty_card(stamps, cfg["stamps_needed"]))
            if st.button("Resgatar"):
                ok, msg = redeem_reward(cid)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        else:
            st.warning("Cliente não encontrado.")

def page_find():
    st.subheader("Buscar cliente por nome")
    q = st.text_input("Digite parte do nome")
    if q:
        rows = find_customer_by_name_like(q)
        if rows:
            for c in rows:
                cid, name, phone, email, stamps, total, created = c
                with st.expander(f"{name} — {phone or 'sem telefone'}"):
                    cfg = get_config()
                    st.write("E-mail:", email or "—")
                    st.write("Carimbos:", stamps, " | Cartão:", loyalty_card(stamps, cfg["stamps_needed"]))
                    st.write("Total gasto: R$ {:.2f}".format(total or 0))
                    st.write("Cadastrado em:", created)
        else:
            st.info("Nenhum cliente encontrado.")

def page_customers():
    st.subheader("Clientes (recentes)")
    rows = list_customers(limit=200)
    if not rows:
        st.info("Sem clientes ainda.")
        return
    cfg = get_config()
    for c in rows:
        cid, name, phone, email, stamps, total, created = c
        cols = st.columns([2,2,2,2])
        with cols[0]:
            st.markdown(f"**{name}**  \n{phone or '—'}")
        with cols[1]:
            st.text(email or "—")
        with cols[2]:
            st.write(f"Carimbos: {stamps}")
            st.write(loyalty_card(stamps, cfg['stamps_needed']))
        with cols[3]:
            st.write("Gasto: R$ {:.2f}".format(total or 0))
            st.write(created)

def page_admin():
    st.subheader("Administração")
    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes", stats["total_customers"])
    c2.metric("Carimbos em carteira", stats["total_stamps"])
    c3.metric("Prêmios resgatados", stats["rewards"])
    c4.metric("Compras registradas", stats["purchases"])
    st.divider()
    cfg = get_config()
    st.write("**Regras do programa**")
    colA, colB = st.columns(2)
    with colA:
        new_needed = st.number_input("Carimbos necessários para prêmio", min_value=1, value=int(cfg["stamps_needed"]), step=1)
    with colB:
        new_rps = st.number_input("R$ por carimbo", min_value=1.0, value=float(cfg["reais_per_stamp"]), step=1.0, format="%.2f")
    if st.button("Salvar regras"):
        set_config(int(new_needed), float(new_rps))
        st.success("Regras atualizadas.")

# -------------------------
# Main
# -------------------------
def main():
    st.set_page_config(page_title="Cartão Fidelidade", page_icon="☕", layout="wide")
    init_db()
    header()
    choice = nav()
    if choice == "Registrar Cliente":
        page_register()
    elif choice == "Nova Compra":
        page_purchase()
    elif choice == "Resgatar Prêmio":
        page_redeem()
    elif choice == "Buscar Cliente":
        page_find()
    elif choice == "Clientes":
        page_customers()
    elif choice == "Admin":
        page_admin()

if __name__ == "__main__":
    main()
