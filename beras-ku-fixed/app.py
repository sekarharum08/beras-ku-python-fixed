from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import os
import sqlite3
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = "beras-ku-mvp-secret-key"
DB = Path(__file__).with_name("beras_ku.db")
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# DATABASE
# =========================
class HybridRow(dict):
    """Row yang bisa diakses dengan nama kolom atau indeks seperti sqlite.Row."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class PgCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
    def fetchone(self):
        row = self.cursor.fetchone()
        return HybridRow(row) if row is not None else None
    def fetchall(self):
        return [HybridRow(row) for row in self.cursor.fetchall()]

class PgConnection:
    def __init__(self, conn):
        self.conn = conn
    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql.replace('?', '%s'), params)
        return PgCursor(cur)
    def executemany(self, sql, params):
        cur = self.conn.cursor()
        cur.executemany(sql.replace('?', '%s'), params)
        return cur
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

def db():
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return PgConnection(psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor))
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    if DATABASE_URL:
        statements = [
            "CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL, price INTEGER NOT NULL, stock INTEGER NOT NULL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, customer_name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, payment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Menunggu Konfirmasi', total INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS order_items (id SERIAL PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, size INTEGER NOT NULL, price INTEGER NOT NULL, qty INTEGER NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(id))"
        ]
        for statement in statements:
            conn.execute(statement)
    else:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL, price INTEGER NOT NULL, stock INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, payment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Menunggu Konfirmasi', total INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, size INTEGER NOT NULL, price INTEGER NOT NULL, qty INTEGER NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(id));
        """)
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        products = [
            ("Beras Premium Pulen", "Premium", 5, 72000, 40),
            ("Beras Premium Pulen", "Premium", 10, 139000, 60),
            ("Beras Medium", "Medium", 5, 60000, 50),
            ("Beras Medium", "Medium", 10, 115000, 80),
            ("Beras Pandan Wangi", "Pandan Wangi", 5, 85000, 30),
            ("Beras Pandan Wangi", "Pandan Wangi", 10, 165000, 40),
        ]
        conn.executemany("INSERT INTO products(name,type,size,price,stock) VALUES(?,?,?,?,?)", products)
    conn.commit()
    conn.close()

def rupiah(value):
    return "Rp{:,.0f}".format(value).replace(",", ".")

# =========================
# AUTH
# =========================
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

# =========================
# TEMPLATE
# =========================
CSS = """
<style>
:root{--green:#176b45;--green2:#21865a;--cream:#faf7f0;--line:#e7e2d8;--text:#222;--muted:#716d65;--danger:#b42318}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Arial;background:var(--cream);color:var(--text)}
a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}
header{height:70px;background:white;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:10}
.brand{display:flex;gap:10px;align-items:center}.logo{width:42px;height:42px;border-radius:13px;background:var(--green);display:grid;place-items:center;color:white;font-size:22px}
.brand b{display:block}.brand small{color:var(--muted)}
nav{display:flex;gap:8px;align-items:center}nav a{padding:9px 12px;border-radius:10px;font-size:14px}nav a:hover{background:#e9f4ed;color:var(--green)}
.container{max-width:1150px;margin:auto;padding:28px 5% 50px}.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:25px;align-items:center;margin-bottom:28px}
.hero h1{font-size:42px;line-height:1.05;margin:8px 0 14px}.hero p{color:var(--muted);line-height:1.7}.hero-card{background:#eaf4ed;border-radius:24px;padding:28px;min-height:210px}.rice{font-size:90px;text-align:center}
.badge{display:inline-block;background:#e7f2eb;color:var(--green);padding:7px 11px;border-radius:999px;font-size:12px;font-weight:800}
.section-title{display:flex;justify-content:space-between;align-items:end;margin:24px 0 14px}.section-title h2,.section-title h3{margin:0}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.toolbar input,.toolbar select,.form input,.form select,.form textarea{border:1px solid var(--line);background:#fff;border-radius:11px;padding:11px 13px;outline:none}.toolbar input{min-width:240px;flex:1}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.product{background:white;border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 5px 20px #00000008}
.product-img{height:145px;background:linear-gradient(135deg,#f4ead4,#e7f1e8);display:grid;place-items:center;font-size:70px}.product-body{padding:16px}.product h3{margin:0 0 6px}.meta{color:var(--muted);font-size:13px}.price{font-size:19px;font-weight:800;color:var(--green);margin:12px 0}
.stock{font-size:12px;margin-bottom:12px}.low{color:#a15c00}.empty{color:var(--danger)}
.primary{border:0;background:var(--green);color:#fff;padding:11px 15px;border-radius:11px;font-weight:700;cursor:pointer}.primary:hover{background:var(--green2)}
.primary.full{width:100%}.secondary{border:1px solid var(--line);background:#fff;padding:10px 13px;border-radius:10px;cursor:pointer}
.danger{border:0;background:#fff0ef;color:var(--danger);padding:9px 12px;border-radius:9px;cursor:pointer}
.alert{padding:11px 14px;background:#fff7df;border:1px solid #f0dfac;border-radius:11px;margin-bottom:15px;font-size:13px}
.success{background:#e9f4ed;border-color:#b7dec6}
.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:15px;overflow:hidden}.table th,.table td{text-align:left;padding:12px;border-bottom:1px solid var(--line);white-space:nowrap}.table th{font-size:11px;text-transform:uppercase;color:var(--muted)}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.stat{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px}.stat small{color:var(--muted)}.stat b{font-size:25px;display:block;margin-top:5px}
.panel{background:#fff;border:1px solid var(--line);border-radius:17px;padding:18px;margin-top:18px}
.form{display:grid;gap:10px}.form label{font-size:12px;font-weight:700}.form textarea{min-height:90px;resize:vertical}
.card{max-width:650px;margin:30px auto;background:white;border:1px solid var(--line);border-radius:20px;padding:24px}.card h2{margin-top:0}
.cart{background:#fff;border:1px solid var(--line);border-radius:17px;padding:18px;margin-top:18px}.cart-row{display:flex;justify-content:space-between;gap:15px;padding:12px 0;border-bottom:1px solid var(--line)}
.qty{display:flex;gap:8px;align-items:center}.qty a{border:1px solid var(--line);border-radius:8px;padding:3px 8px}
.total{display:flex;justify-content:space-between;font-size:19px;font-weight:800;padding:15px 0}
.status{display:inline-block;padding:5px 9px;border-radius:999px;background:#e9f4ed;color:var(--green);font-size:11px;font-weight:800}
footer{text-align:center;color:var(--muted);font-size:12px;padding:25px}
@media(max-width:800px){.hero{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}.stat-grid{grid-template-columns:repeat(2,1fr)}header{padding:0 3%}.container{padding-left:3%;padding-right:3%}}
@media(max-width:520px){.grid{grid-template-columns:1fr}.hero h1{font-size:34px}.hero-card{display:none}.stat-grid{grid-template-columns:1fr 1fr}nav a{font-size:12px;padding:7px}}
</style>
"""

BASE = """
<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} - BerasKu</title>""" + CSS + """</head><body>
<header>
<div class="brand"><div class="logo">🌾</div><div><b>BerasKu</b><small>Toko Beras Online</small></div></div>
<nav>
<a href="/">Belanja</a>
<a href="/orders">Pesanan</a>
<a href="/admin">Admin</a>
</nav>
</header>
{% with messages=get_flashed_messages(with_categories=true) %}
{% for category,message in messages %}
<div class="container" style="padding-bottom:0"><div class="alert {{'success' if category=='success' else ''}}">{{message}}</div></div>
{% endfor %}
{% endwith %}
{{ body|safe }}
<footer>BerasKu MVP • Sistem Pemesanan Toko Beras</footer>
</body></html>
"""

def page(title, body):
    return render_template_string(BASE, title=title, body=body)

# =========================
# CUSTOMER
# =========================
@app.route("/")
def home():
    conn = db()
    q = request.args.get("q","").strip()
    size = request.args.get("size","")
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR type LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if size:
        sql += " AND size=?"
        params.append(int(size))
    products = conn.execute(sql+" ORDER BY id", params).fetchall()
    conn.close()

    cart = session.get("cart", {})
    count = sum(cart.values())

    cards = ""
    for p in products:
        stock_class = "empty" if p["stock"] == 0 else ("low" if p["stock"] <= 10 else "")
        cards += f"""
        <article class="product">
          <div class="product-img">🌾</div>
          <div class="product-body">
            <h3>{p['name']}</h3>
            <div class="meta">{p['type']} • {p['size']} kg</div>
            <div class="price">{rupiah(p['price'])}</div>
            <div class="stock {stock_class}">
              {'Stok habis' if p['stock']==0 else f"Stok {p['stock']} kg"}
            </div>
            {'<span style="color:#b42318;font-size:12px">Tidak tersedia</span>' if p['stock']==0 else f'<a class="primary" style="display:block;text-align:center" href="/cart/add/{p["id"]}">+ Keranjang</a>'}
          </div>
        </article>
        """

    body = f"""
    <main class="container">
      <section class="hero">
        <div>
          <span class="badge">MVP • Pemesanan Online</span>
          <h1>Beras pilihan untuk kebutuhan sehari-hari.</h1>
          <p>BerasKu adalah prototype sistem pemesanan beras dengan alur sederhana:
          pilih produk, masukkan keranjang, checkout, lalu pantau status pesanan.</p>
        </div>
        <div class="hero-card"><div class="rice">🌾</div><b>Praktis dan sederhana.</b>
        <div class="meta">Produk → Keranjang → Checkout → Status</div></div>
      </section>

      <div class="section-title"><h2>Produk Beras</h2><span>{len(products)} pilihan</span></div>
      <form class="toolbar" method="get">
        <input name="q" value="{q}" placeholder="Cari jenis beras...">
        <select name="size">
          <option value="">Semua ukuran</option>
          <option value="5" {'selected' if size=='5' else ''}>5 kg</option>
          <option value="10" {'selected' if size=='10' else ''}>10 kg</option>
        </select>
        <button class="primary" type="submit">Cari</button>
      </form>
      <div class="grid">{cards or '<div class="panel">Produk tidak ditemukan.</div>'}</div>

      <div class="cart">
        🛒 Keranjang: <b>{count} item</b>
        <a class="primary" style="float:right" href="/cart">Buka Keranjang</a>
      </div>
    </main>
    """
    return page("Belanja", body)

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    conn = db()
    items = []
    total = 0
    for pid, qty in cart_data.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (int(pid),)).fetchone()
        if p:
            subtotal = p["price"] * qty
            total += subtotal
            items.append((p, qty, subtotal))
    conn.close()

    rows = ""
    for p, qty, subtotal in items:
        rows += f"""
        <div class="cart-row">
          <div><b>{p['name']}</b><div class="meta">{p['type']} • {p['size']} kg • {rupiah(p['price'])}</div></div>
          <div>
            <div class="qty">
              <a href="/cart/dec/{p['id']}">−</a><b>{qty}</b><a href="/cart/inc/{p['id']}">+</a>
              <a class="danger" href="/cart/remove/{p['id']}">Hapus</a>
            </div>
            <div style="text-align:right;margin-top:6px"><b>{rupiah(subtotal)}</b></div>
          </div>
        </div>
        """

    body = f"""
    <main class="container">
      <div class="section-title"><h2>Keranjang</h2><a href="/">← Lanjut Belanja</a></div>
      <div class="cart">
        {rows or '<div style="text-align:center;padding:30px;color:#716d65">Keranjang masih kosong.</div>'}
        <div class="total"><span>Total</span><span>{rupiah(total)}</span></div>
        {'<a class="primary" style="display:block;text-align:center" href="/checkout">Lanjut Checkout</a>' if items else ''}
      </div>
    </main>
    """
    return page("Keranjang", body)

def cart_change(pid, delta):
    cart = session.get("cart", {})
    key = str(pid)
    conn = db()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not p:
        return redirect("/cart")
    current = cart.get(key, 0)
    new_qty = current + delta
    if new_qty < 0:
        new_qty = 0
    if new_qty * p["size"] > p["stock"]:
        flash("Jumlah melebihi stok yang tersedia.", "error")
        return redirect("/cart")
    if new_qty == 0:
        cart.pop(key, None)
    else:
        cart[key] = new_qty
    session["cart"] = cart
    return redirect("/cart")

@app.route("/cart/add/<int:pid>")
def cart_add(pid):
    return cart_change(pid, 1)

@app.route("/cart/inc/<int:pid>")
def cart_inc(pid):
    return cart_change(pid, 1)

@app.route("/cart/dec/<int:pid>")
def cart_dec(pid):
    return cart_change(pid, -1)

@app.route("/cart/remove/<int:pid>")
def cart_remove(pid):
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect("/cart")

@app.route("/checkout", methods=["GET","POST"])
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Keranjang masih kosong.", "error")
        return redirect("/cart")

    conn = db()
    items = []
    total = 0
    for pid, qty in cart_data.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (int(pid),)).fetchone()
        if not p or qty * p["size"] > p["stock"]:
            conn.close()
            flash("Stok salah satu produk tidak mencukupi.", "error")
            return redirect("/cart")
        total += p["price"] * qty
        items.append((p, qty))

    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        payment = request.form.get("payment", "COD")
        if payment not in ("COD", "Transfer Bank", "QRIS"):
            conn.close()
            flash("Metode pembayaran tidak valid.", "error")
            return redirect("/checkout")

        if not name or not phone or not address:
            conn.close()
            flash("Nama, WhatsApp, dan alamat wajib diisi.", "error")
            return redirect("/checkout")

        if DATABASE_URL:
            cur = conn.execute("""
                INSERT INTO orders(customer_name,phone,address,payment,total)
                VALUES(?,?,?,?,?) RETURNING id
            """, (name, phone, address, payment, total))
            order_id = cur.fetchone()["id"]
        else:
            cur = conn.execute("""
                INSERT INTO orders(customer_name,phone,address,payment,total)
                VALUES(?,?,?,?,?)
            """, (name, phone, address, payment, total))
            order_id = cur.lastrowid

        for p, qty in items:
            conn.execute("""
                INSERT INTO order_items(order_id,product_id,product_name,size,price,qty)
                VALUES(?,?,?,?,?,?)
            """, (order_id, p["id"], p["name"], p["size"], p["price"], qty))
            conn.execute("UPDATE products SET stock=stock-? WHERE id=?",
                         (qty*p["size"], p["id"]))

        conn.commit()
        conn.close()
        session["cart"] = {}
        flash(f"Pesanan BR-{order_id:06d} berhasil dibuat.", "success")
        return redirect("/orders")

    conn.close()

    body = """
    <main class="container">
      <div class="card">
        <h2>Checkout</h2>
        <div class="alert">Status awal pesanan: <b>Menunggu Konfirmasi</b></div>
        <form class="form" method="post">
          <label>Nama Pelanggan<input name="name" placeholder="Nama lengkap" required></label>
          <label>No. WhatsApp<input name="phone" placeholder="08xxxxxxxxxx" required></label>
          <label>Alamat Pengiriman<textarea name="address" placeholder="Alamat lengkap" required></textarea></label>
          <label>Metode Pembayaran
            <select name="payment" id="payment" onchange="showPaymentInfo()">
              <option value="COD">COD</option>
              <option value="Transfer Bank">Transfer Bank</option>
              <option value="QRIS">QRIS</option>
            </select>
          </label>
          <div id="transfer-info" class="panel" style="display:none">
            <h3>Informasi Transfer Bank</h3>
            <p>Bank: BCA</p><p>Nomor rekening: 0056784320</p><p>Atas nama: Toko Beras</p>
          </div>
          <div id="qris-info" class="panel" style="display:none;text-align:center">
            <h3>Bayar dengan QRIS</h3>
            <img src="/static/qris.jpeg" alt="QRIS toko" onerror="this.style.display='none'" style="width:100%;max-width:280px;height:auto">
            <p>Scan kode QR menggunakan aplikasi pembayaran kamu.</p>
          </div>
          <button class="primary full" type="submit">Buat Pesanan</button>
        </form>
      </div>
    </main>
    <script>
    function showPaymentInfo() {
      const payment = document.getElementById('payment').value;
      document.getElementById('transfer-info').style.display = payment === 'Transfer Bank' ? 'block' : 'none';
      document.getElementById('qris-info').style.display = payment === 'QRIS' ? 'block' : 'none';
    }
    showPaymentInfo();
    </script>
    """
    return page("Checkout", body)

@app.route("/orders")
def orders():
    conn = db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    result = ""
    for o in orders:
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
        item_text = "<br>".join(
            f"{i['product_name']} {i['size']} kg × {i['qty']}" for i in items
        )
        result += f"""
        <div class="panel">
          <div class="section-title"><h3>BR-{o['id']:06d}</h3><span class="status">{o['status']}</span></div>
          <div class="meta">{o['created_at']} • {o['payment']}</div>
          <p><b>{o['customer_name']}</b> • {o['phone']}<br>{o['address']}</p>
          <div>{item_text}</div>
          <div class="total"><span>Total</span><span>{rupiah(o['total'])}</span></div>
        </div>
        """
    conn.close()

    body = f"""
    <main class="container">
      <div class="section-title"><h2>Pesanan</h2><a href="/">← Kembali Belanja</a></div>
      {result or '<div class="panel" style="text-align:center">Belum ada pesanan.</div>'}
    </main>
    """
    return page("Pesanan", body)

# =========================
# ADMIN
# =========================
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["admin"] = True
            return redirect("/admin")
        flash("Username atau password salah.", "error")

    body = """
    <main class="container">
      <div class="card">
        <h2>Login Admin</h2>
        <div class="alert">Demo: username <b>admin</b>, password <b>admin123</b>.</div>
        <form class="form" method="post">
          <label>Username<input name="username" value="admin"></label>
          <label>Password<input name="password" type="password"></label>
          <button class="primary full">Masuk</button>
        </form>
      </div>
    </main>
    """
    return page("Login Admin", body)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")

@app.route("/admin")
@admin_required
def admin():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    total_stock = sum(p["stock"] for p in products)
    customers = conn.execute("SELECT COUNT(DISTINCT phone) FROM orders").fetchone()[0]
    conn.close()

    product_rows = "".join(f"""
    <tr>
      <td>{p['name']}<br><small>{p['type']}</small></td>
      <td>{p['size']} kg</td><td>{rupiah(p['price'])}</td><td>{p['stock']} kg</td>
      <td><a class="secondary" href="/admin/product/edit/{p['id']}">Edit</a>
          <a class="danger" href="/admin/product/delete/{p['id']}" onclick="return confirm('Hapus produk?')">Hapus</a></td>
    </tr>""" for p in products)

    order_rows = "".join(f"""
    <tr><td>BR-{o['id']:06d}</td><td>{o['customer_name']}</td><td>{rupiah(o['total'])}</td>
    <td><span class="status">{o['status']}</span></td>
    <td>
      <form method="post" action="/admin/order/{o['id']}/status">
      <select name="status" onchange="this.form.submit()">
        {''.join(f'<option {"selected" if o["status"]==s else ""}>{s}</option>' for s in ["Menunggu Konfirmasi","Diproses","Dikirim","Selesai","Dibatalkan"])}
      </select></form>
    </td></tr>""" for o in orders)

    body = f"""
    <main class="container">
      <div class="section-title"><h2>Dashboard Admin</h2><a href="/admin/logout">Keluar</a></div>
      <div class="stat-grid">
        <div class="stat"><small>Total Produk</small><b>{len(products)}</b></div>
        <div class="stat"><small>Total Stok</small><b>{total_stock} kg</b></div>
        <div class="stat"><small>Total Pelanggan</small><b>{customers}</b></div>
        <div class="stat"><small>Total Pesanan</small><b>{len(orders)}</b></div>
      </div>

      <div class="panel">
        <div class="section-title"><h3>Produk</h3><a class="primary" href="/admin/product/new">+ Tambah Produk</a></div>
        <div class="table-wrap"><table class="table"><thead><tr>
        <th>Produk</th><th>Ukuran</th><th>Harga</th><th>Stok</th><th>Aksi</th>
        </tr></thead><tbody>{product_rows}</tbody></table></div>
      </div>

      <div class="panel">
        <div class="section-title"><h3>Pesanan</h3><span>Ubah status langsung dari tabel</span></div>
        <div class="table-wrap"><table class="table"><thead><tr>
        <th>ID</th><th>Pelanggan</th><th>Total</th><th>Status</th><th>Ubah Status</th>
        </tr></thead><tbody>{order_rows or '<tr><td colspan="5">Belum ada pesanan.</td></tr>'}</tbody></table></div>
      </div>
    </main>
    """
    return page("Admin", body)

@app.route("/admin/product/new", methods=["GET","POST"])
@admin_required
def product_new():
    return product_form()

@app.route("/admin/product/edit/<int:pid>", methods=["GET","POST"])
@admin_required
def product_edit(pid):
    return product_form(pid)

def product_form(pid=None):
    conn = db()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone() if pid else None

    if request.method == "POST":
        name = request.form["name"].strip()
        typ = request.form["type"].strip()
        size = int(request.form["size"])
        price = int(request.form["price"])
        stock = int(request.form["stock"])

        if pid:
            conn.execute("""UPDATE products SET name=?,type=?,size=?,price=?,stock=? WHERE id=?""",
                         (name, typ, size, price, stock, pid))
            msg = "Produk berhasil diperbarui."
        else:
            conn.execute("""INSERT INTO products(name,type,size,price,stock) VALUES(?,?,?,?,?)""",
                         (name, typ, size, price, stock))
            msg = "Produk berhasil ditambahkan."
        conn.commit()
        conn.close()
        flash(msg, "success")
        return redirect("/admin")

    conn.close()

    body = f"""
    <main class="container">
      <div class="card">
        <h2>{'Edit Produk' if p else 'Tambah Produk'}</h2>
        <form class="form" method="post">
          <label>Nama Produk<input name="name" value="{p['name'] if p else ''}" required></label>
          <label>Jenis<input name="type" value="{p['type'] if p else ''}" placeholder="Premium / Medium / Pandan Wangi" required></label>
          <label>Ukuran<select name="size">
            <option value="5" {'selected' if p and p['size']==5 else ''}>5 kg</option>
            <option value="10" {'selected' if p and p['size']==10 else ''}>10 kg</option>
          </select></label>
          <label>Harga<input name="price" type="number" value="{p['price'] if p else ''}" required></label>
          <label>Stok (kg)<input name="stock" type="number" value="{p['stock'] if p else 0}" required></label>
          <button class="primary full">Simpan</button>
        </form>
      </div>
    </main>
    """
    return page("Produk", body)

@app.route("/admin/product/delete/<int:pid>")
@admin_required
def product_delete(pid):
    conn = db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Produk berhasil dihapus.", "success")
    return redirect("/admin")

@app.route("/admin/order/<int:oid>/status", methods=["POST"])
@admin_required
def order_status(oid):
    status = request.form["status"]
    conn = db()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()
    flash("Status pesanan diperbarui.", "success")
    return redirect("/admin")

# =========================
# RUN
# =========================
# Vercel mengimpor modul sebagai aplikasi; inisialisasi tabel saat cold start.
try:
    init_db()
except Exception:
    app.logger.exception("Gagal menginisialisasi database")

if __name__ == "__main__":
    print("=" * 55)
    print("BerasKu MVP berjalan di http://127.0.0.1:5000")
    print("Admin: http://127.0.0.1:5000/admin")
    print("Username: admin")
    print("Password: admin123")
    print("=" * 55)
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
