import os, io, json
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.metrics import mean_absolute_error
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for d in ['uploads','database','reports']:
    os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY']                  = 'sarthak-argade-nexus-2024'
app.config['SQLALCHEMY_DATABASE_URI']     = 'sqlite:///' + os.path.join(BASE_DIR,'database','nexus.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH']          = 16 * 1024 * 1024

db           = SQLAlchemy(app)
bcrypt       = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view    = 'login'
login_manager.login_message = ''

# ─── Models ───────────────────────────────────────────────────────────────────
class User(db.Model, UserMixin):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(20),  default='analyst')
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)
    datasets   = db.relationship('Dataset', backref='owner', lazy=True)

class Dataset(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    filename    = db.Column(db.String(200), nullable=False)
    rows        = db.Column(db.Integer)
    columns     = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

# ─── Demo Data ────────────────────────────────────────────────────────────────
def generate_demo_data():
    np.random.seed(42)
    n = 600
    products = ['Laptop Pro','Wireless Mouse','USB-C Hub','Monitor 4K',
                'Keyboard RGB','Webcam HD','SSD 1TB','Headphones','Desk Lamp','Cable Organizer']
    cats  = {'Laptop Pro':'Electronics','Wireless Mouse':'Peripherals','USB-C Hub':'Accessories',
             'Monitor 4K':'Electronics','Keyboard RGB':'Peripherals','Webcam HD':'Electronics',
             'SSD 1TB':'Storage','Headphones':'Audio','Desk Lamp':'Office','Cable Organizer':'Accessories'}
    price = {'Laptop Pro':1200,'Wireless Mouse':45,'USB-C Hub':65,'Monitor 4K':800,
             'Keyboard RGB':120,'Webcam HD':150,'SSD 1TB':110,'Headphones':200,'Desk Lamp':40,'Cable Organizer':20}
    regions   = ['North','South','East','West','Central']
    customers = [f'Customer_{i:03d}' for i in range(1,101)]
    dates = pd.date_range('2023-01-01','2024-12-31', periods=n)
    prods = np.random.choice(products, n)
    sales = [price[p]*np.random.uniform(0.8,1.4)*np.random.randint(1,6) for p in prods]
    return pd.DataFrame({
        'Date':          dates,
        'Product':       prods,
        'Category':      [cats[p] for p in prods],
        'Region':        np.random.choice(regions, n),
        'Sales':         [round(s,2) for s in sales],
        'Profit':        [round(s*np.random.uniform(0.15,0.40),2) for s in sales],
        'Quantity':      [int(np.random.randint(1,6)) for _ in prods],
        'Customer_Name': np.random.choice(customers, n),
    })

# ─── Data helpers ─────────────────────────────────────────────────────────────
def load_data(user_id):
    ds = Dataset.query.filter_by(user_id=user_id).order_by(Dataset.uploaded_at.desc()).first()
    if ds:
        fp = os.path.join(BASE_DIR,'uploads',ds.filename)
        if os.path.exists(fp):
            try:
                ext = ds.filename.rsplit('.',1)[-1].lower()
                df  = pd.read_csv(fp) if ext=='csv' else pd.read_excel(fp)
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                for col in ['Sales','Profit','Quantity']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                return df
            except Exception:
                pass
    return generate_demo_data()

def apply_filters(df, f):
    dff = df.copy()
    try:
        if f.get('date_from','').strip():
            dff = dff[dff['Date'] >= pd.to_datetime(f['date_from'])]
        if f.get('date_to','').strip():
            dff = dff[dff['Date'] <= pd.to_datetime(f['date_to'])]
    except Exception:
        pass
    if f.get('category','all') not in ('','all'):
        dff = dff[dff['Category'] == f['category']]
    if f.get('region','all') not in ('','all'):
        dff = dff[dff['Region'] == f['region']]
    if f.get('product','all') not in ('','all'):
        dff = dff[dff['Product'] == f['product']]
    return dff if len(dff) > 0 else df   # fallback to unfiltered if nothing matches

def compute_kpis(df):
    if len(df)==0:
        return dict(total_revenue=0,total_orders=0,total_customers=0,
                    avg_order_value=0,best_product='N/A',monthly_growth=0,
                    total_profit=0,profit_margin=0)
    rev    = float(df['Sales'].sum())
    profit = float(df['Profit'].sum()) if 'Profit' in df.columns else 0
    mid    = len(df)//2
    dfs    = df.sort_values('Date')
    f1,f2  = float(dfs.iloc[:mid]['Sales'].sum()), float(dfs.iloc[mid:]['Sales'].sum())
    return dict(
        total_revenue   = round(rev,2),
        total_orders    = len(df),
        total_customers = int(df['Customer_Name'].nunique()) if 'Customer_Name' in df.columns else 0,
        avg_order_value = round(float(df['Sales'].mean()),2),
        best_product    = df.groupby('Product')['Sales'].sum().idxmax() if 'Product' in df.columns else 'N/A',
        monthly_growth  = round((f2-f1)/f1*100,1) if f1>0 else 0,
        total_profit    = round(profit,2),
        profit_margin   = round(profit/rev*100,1) if rev>0 else 0,
    )

def safe_float_list(series):
    return [round(float(v),2) for v in series]

# ─── Chart data builder ───────────────────────────────────────────────────────
def build_chartdata(df):
    # 1. Monthly trend
    mon = df.groupby(df['Date'].dt.to_period('M')).agg({'Sales':'sum','Profit':'sum'}).reset_index()
    mon['Date'] = mon['Date'].astype(str)

    # 2. Region donut
    reg = df.groupby('Region')['Sales'].sum().reset_index() if 'Region' in df.columns else pd.DataFrame(columns=['Region','Sales'])

    # 3. Top products (horizontal bar)
    top_prod = df.groupby('Product')['Sales'].sum().nlargest(8).reset_index() if 'Product' in df.columns else pd.DataFrame(columns=['Product','Sales'])

    # 4. Customer segments
    seg_labels,seg_values = ['Bronze','Silver','Gold','Platinum'],[0,0,0,0]
    if 'Customer_Name' in df.columns:
        cust = df.groupby('Customer_Name')['Sales'].sum()
        seg  = pd.cut(cust, bins=[0,500,2000,5000,1e9], labels=['Bronze','Silver','Gold','Platinum'])
        counts = seg.value_counts().reindex(['Bronze','Silver','Gold','Platinum'],fill_value=0)
        seg_values = [int(v) for v in counts.values]

    # 5. Revenue vs Profit by product
    pvp = {'labels':[],'sales':[],'profit':[]}
    if 'Product' in df.columns and 'Profit' in df.columns:
        pp = df.groupby('Product').agg({'Sales':'sum','Profit':'sum'}).reset_index()
        pvp = {'labels':pp['Product'].tolist(),
               'sales':safe_float_list(pp['Sales']),
               'profit':safe_float_list(pp['Profit'])}

    # 6. Category pie
    cat_d = {'labels':[],'values':[]}
    if 'Category' in df.columns:
        cat   = df.groupby('Category')['Sales'].sum().reset_index()
        cat_d = {'labels':cat['Category'].tolist(),'values':safe_float_list(cat['Sales'])}

    # 7. Weekly sales (last 12 weeks)
    df2 = df.copy()
    df2['Week'] = df2['Date'].dt.to_period('W')
    weekly = df2.groupby('Week')['Sales'].sum().tail(12).reset_index()
    weekly['Week'] = weekly['Week'].astype(str)

    # 8. Quantity by product
    qty_d = {'labels':[],'values':[]}
    if 'Product' in df.columns and 'Quantity' in df.columns:
        qty   = df.groupby('Product')['Quantity'].sum().nlargest(8).reset_index()
        qty_d = {'labels':qty['Product'].tolist(),'values':[int(v) for v in qty['Quantity']]}

    return {
        'kpis':    compute_kpis(df),
        'monthly': {'labels':mon['Date'].tolist(),'sales':safe_float_list(mon['Sales']),'profit':safe_float_list(mon['Profit'])},
        'region':  {'labels':reg['Region'].tolist(),'values':safe_float_list(reg['Sales'])} if len(reg) else {'labels':[],'values':[]},
        'product': {'labels':top_prod['Product'].tolist(),'values':safe_float_list(top_prod['Sales'])} if len(top_prod) else {'labels':[],'values':[]},
        'segments':{'labels':seg_labels,'values':seg_values},
        'pvp':     pvp,
        'category':cat_d,
        'weekly':  {'labels':weekly['Week'].tolist(),'values':safe_float_list(weekly['Sales'])},
        'qty':     qty_d,
    }

# ─── Forecast ─────────────────────────────────────────────────────────────────
def build_forecast(df):
    mon = df.groupby(df['Date'].dt.to_period('M'))['Sales'].sum().reset_index()
    mon.columns = ['Month','Sales']
    mon['n'] = range(len(mon))
    if len(mon) < 3:
        return None, None, []

    X,y = mon[['n']].values, mon['Sales'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X,y)

    fp    = model.predict([[len(mon)+i] for i in range(6)])
    ci    = fp * 0.10
    last  = mon['Month'].iloc[-1].to_timestamp()
    fdates= [(last+pd.DateOffset(months=i+1)).strftime('%Y-%m') for i in range(6)]

    insights = {
        'trend':   'upward' if fp[-1]>fp[0] else 'downward',
        'next':    round(float(fp[0]),2),
        'sixth':   round(float(fp[-1]),2),
        'change':  round(abs((fp[-1]-fp[0])/fp[0]*100),1) if fp[0] else 0,
        'mae':     round(float(mean_absolute_error(y, model.predict(X))),2),
    }

    # anomaly detection
    iso  = IsolationForest(contamination=0.1, random_state=42)
    mon['flag'] = iso.fit_predict(mon[['Sales']])
    anom = mon[mon['flag']==-1][['Month','Sales']].copy()
    anom_list = [{'month':str(r['Month']),'sales':round(float(r['Sales']),2)} for _,r in anom.iterrows()]

    # product trends
    df2 = df.copy(); df2['Month'] = df['Date'].dt.to_period('M')
    mx  = df2['Month'].max()
    rec = df2[df2['Month'] >= mx-2]; old = df2[df2['Month'] < mx-2]
    top,dec = {},{}
    if len(old)>0 and len(rec)>0 and 'Product' in df.columns:
        rp,op = rec.groupby('Product')['Sales'].sum(), old.groupby('Product')['Sales'].sum()
        common = rp.index.intersection(op.index)
        if len(common):
            chg = ((rp[common]-op[common])/op[common]*100)
            top = {k:round(float(v),1) for k,v in chg.nlargest(3).items()}
            dec = {k:round(float(v),1) for k,v in chg.nsmallest(3).items()}

    return {
        'hist_labels':   mon['Month'].astype(str).tolist(),
        'hist_values':   safe_float_list(y),
        'future_labels': fdates,
        'future_values': safe_float_list(fp),
        'upper':         safe_float_list(fp+ci),
        'lower':         safe_float_list(fp-ci),
    }, insights, anom_list, top, dec

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method=='POST':
        u,e,p,c = (request.form.get(k,'').strip() for k in ['username','email','password','confirm_password'])
        if not u or not e or not p:             flash('All fields required.','error')
        elif p!=c:                              flash('Passwords do not match.','error')
        elif len(p)<6:                          flash('Password min 6 characters.','error')
        elif User.query.filter_by(username=u).first(): flash('Username taken.','error')
        elif User.query.filter_by(email=e).first():    flash('Email already registered.','error')
        else:
            db.session.add(User(username=u,email=e,password=bcrypt.generate_password_hash(p).decode()))
            db.session.commit()
            login_user(User.query.filter_by(username=u).first())
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method=='POST':
        u,p = request.form.get('username','').strip(), request.form.get('password','')
        user = User.query.filter_by(username=u).first()
        if user and bcrypt.check_password_hash(user.password,p):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.','error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    df       = load_data(current_user.id)
    kpis     = compute_kpis(df)
    datasets = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    cats     = sorted(df['Category'].dropna().unique().tolist()) if 'Category' in df.columns else []
    regions  = sorted(df['Region'].dropna().unique().tolist())   if 'Region'   in df.columns else []
    products = sorted(df['Product'].dropna().unique().tolist())  if 'Product'  in df.columns else []
    return render_template('dashboard.html', kpis=kpis, datasets=datasets,
                           categories=cats, regions=regions, products=products,
                           username=current_user.username)

# ─── API: chart data (filters supported) ──────────────────────────────────────
@app.route('/api/chartdata')
@login_required
def api_chartdata():
    f  = {k: request.args.get(k,'') for k in ['date_from','date_to','category','region','product']}
    df = apply_filters(load_data(current_user.id), f)
    return jsonify(build_chartdata(df))

# ─── API: forecast ─────────────────────────────────────────────────────────────
@app.route('/api/forecast')
@login_required
def api_forecast():
    df = load_data(current_user.id)
    fc, ins, anom, top, dec = build_forecast(df)
    if fc is None:
        return jsonify({'error':'Need at least 3 months of data.'}), 400
    return jsonify({'forecast':fc,'insights':ins,'anomalies':anom,'top_products':top,'declining':dec})

# ─── API: table ────────────────────────────────────────────────────────────────
@app.route('/api/table')
@login_required
def api_table():
    f  = {k: request.args.get(k,'') for k in ['date_from','date_to','category','region','product']}
    df = apply_filters(load_data(current_user.id), f)
    out = df.sort_values('Date',ascending=False).head(200).copy()
    out['Date'] = out['Date'].dt.strftime('%Y-%m-%d')
    return jsonify(out.fillna('').to_dict('records'))

# ─── API: search ───────────────────────────────────────────────────────────────
@app.route('/api/search')
@login_required
def api_search():
    q  = request.args.get('q','').strip().lower()
    df = load_data(current_user.id)
    if q:
        mask = df.apply(lambda r: r.astype(str).str.lower().str.contains(q,regex=False).any(), axis=1)
        df = df[mask]
    out = df.head(100).copy()
    out['Date'] = out['Date'].dt.strftime('%Y-%m-%d')
    return jsonify(out.fillna('').to_dict('records'))

# ─── Upload ────────────────────────────────────────────────────────────────────
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files: return jsonify({'error':'No file'}),400
    f = request.files['file']
    if not f.filename: return jsonify({'error':'Empty filename'}),400
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in ['csv','xlsx','xls']: return jsonify({'error':'Only CSV/Excel supported'}),400
    fname = f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    fpath = os.path.join(BASE_DIR,'uploads',fname)
    f.save(fpath)
    try:
        df = pd.read_csv(fpath) if ext=='csv' else pd.read_excel(fpath)
        if 'Date' not in df.columns or 'Sales' not in df.columns:
            os.remove(fpath); return jsonify({'error':'File needs Date and Sales columns'}),400
        db.session.add(Dataset(name=f.filename,filename=fname,rows=len(df),columns=len(df.columns),user_id=current_user.id))
        db.session.commit()
        return jsonify({'success':True,'rows':len(df),'columns':len(df.columns),'name':f.filename})
    except Exception as e:
        if os.path.exists(fpath): os.remove(fpath)
        return jsonify({'error':str(e)}),400

# ─── Exports ───────────────────────────────────────────────────────────────────
@app.route('/export/csv')
@login_required
def export_csv():
    f  = {k: request.args.get(k,'') for k in ['date_from','date_to','category','region','product']}
    df = apply_filters(load_data(current_user.id), f)
    out = io.StringIO(); df.to_csv(out,index=False); out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode()), mimetype='text/csv',
                     as_attachment=True, download_name=f'nexus_export_{datetime.now().strftime("%Y%m%d")}.csv')

@app.route('/export/pdf')
@login_required
def export_pdf():
    df   = load_data(current_user.id)
    kpis = compute_kpis(df)
    fp   = os.path.join(BASE_DIR,'reports',f'report_{current_user.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf')
    doc  = SimpleDocTemplate(fp, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    st   = getSampleStyleSheet()
    ts   = ParagraphStyle('T',parent=st['Title'],fontSize=22,textColor=colors.HexColor('#00d084'),spaceAfter=10,alignment=TA_CENTER)
    hs   = ParagraphStyle('H',parent=st['Heading2'],fontSize=13,textColor=colors.HexColor('#00d084'),spaceBefore=14,spaceAfter=6)
    ns   = ParagraphStyle('N',parent=st['Normal'],fontSize=9)
    story = [
        Paragraph('NEXUS Analytics — Sarthak Argade', ts),
        Paragraph(f'Generated: {datetime.now().strftime("%B %d, %Y %H:%M")} | User: {current_user.username}', ns),
        Spacer(1,14), Paragraph('KPI Summary', hs),
    ]
    rows = [['Metric','Value'],
            ['Total Revenue',    f'${kpis["total_revenue"]:,.2f}'],
            ['Total Orders',     f'{kpis["total_orders"]:,}'],
            ['Total Customers',  f'{kpis["total_customers"]:,}'],
            ['Avg Order Value',  f'${kpis["avg_order_value"]:,.2f}'],
            ['Total Profit',     f'${kpis["total_profit"]:,.2f}'],
            ['Profit Margin',    f'{kpis["profit_margin"]}%'],
            ['Growth',           f'{kpis["monthly_growth"]}%'],
            ['Best Product',      kpis["best_product"]]]
    t = Table(rows,colWidths=[3*inch,3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#00d084')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f5f5f5'),colors.white]),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cccccc')),
        ('PADDING',(0,0),(-1,-1),7),
    ]))
    story += [t, Spacer(1,14), Paragraph('Top Products', hs)]
    tp = df.groupby('Product')['Sales'].sum().nlargest(5).reset_index()
    pr = [['Product','Revenue']]+[[r['Product'],f'${r["Sales"]:,.2f}'] for _,r in tp.iterrows()]
    pt = Table(pr,colWidths=[3*inch,3*inch])
    pt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#111820')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f5f5f5'),colors.white]),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cccccc')),
        ('PADDING',(0,0),(-1,-1),7),
    ]))
    story.append(pt)
    doc.build(story)
    return send_file(fp,mimetype='application/pdf',as_attachment=True,
                     download_name=f'nexus_report_{datetime.now().strftime("%Y%m%d")}.pdf')

# ─── Boot ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='demo').first():
            db.session.add(User(username='demo',email='demo@nexus.ai',
                                password=bcrypt.generate_password_hash('demo123').decode(),role='admin'))
            db.session.commit()
            print('✓ Demo user ready — demo / demo123')
    app.run(debug=True, host='0.0.0.0', port=5000)
