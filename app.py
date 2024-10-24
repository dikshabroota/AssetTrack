from flask import Flask, request, redirect, url_for, session, render_template
from firebase_admin import auth

import firebase_admin
from firebase_admin import credentials, firestore, auth
import requests

import matplotlib
matplotlib.use('Agg')  # Use the non-interactive Agg backend for image generation

import matplotlib.pyplot as plt
import config


# Path to the Firebase Admin SDK JSON file
cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)

# Initialize the Firebase app with the service account
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()
app = Flask(__name__)
app.secret_key = config.SECRET_KEY  # This generates a random 24-byte key

# Replace with your Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = config.ALPHA_VANTAGE_API_KEY



def get_stock_price(symbol):
    base_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={ALPHA_VANTAGE_API_KEY}'
    response = requests.get(base_url)
    data = response.json()
    
    # Extract the latest close price from the response
    try:
        time_series = data['Time Series (5min)']
        latest_time = list(time_series.keys())[0]  # Get the most recent time
        latest_price = float(time_series[latest_time]['4. close'])
        return latest_price
    except KeyError:
        return None  # Handle the case when stock data is unavailable
    


def get_crypto_price(crypto_id):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd'
    response = requests.get(url)
    data = response.json()

    # Check if the 'crypto_id' exists in the response
    if crypto_id in data:
        return data[crypto_id]['usd']
    else:
        return None  # Handle the case when the cryptocurrency is not found





def plot_asset_value_pi_chart(portfolio_data):
    asset_summary = {}
    
    # Summarize the portfolio by asset type
    for asset in portfolio_data:
        asset_type = asset['type']
        asset_value = asset['quantity'] * asset['purchase_price']

        if asset_type in asset_summary:
            asset_summary[asset_type] += asset_value
        else:
            asset_summary[asset_type] = asset_value

    # Prepare data for pie chart
    labels = list(asset_summary.keys())
    sizes = list(asset_summary.values())
    
    colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0','#ffb3e6']  # Custom colors

    # Generate the pie chart
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90, 
            explode=None, textprops={'fontsize': 12, 'weight': 'bold'})
    
    plt.tight_layout()  # Adjusts layout so that labels are not cut off
    
    # Add a bit more space to prevent text cut-off
    plt.subplots_adjust(left=0.2, right=0.8, top=0.9, bottom=0.1)
    plt.axis('equal')  # Equal aspect ratio ensures that pie chart is drawn as a circle.
    plt.title('Portfolio Distribution', fontsize=16, weight='bold')

    # Add a legend
    plt.legend(labels, loc="best")

    # Save the pie chart image to the static folder
    chart_path = 'static/pie_chart.png'
    plt.savefig(chart_path)
    plt.close()

    return chart_path


    

def plot_asset_value_bar_chart(portfolio_data):
    asset_summary = {}
    
    # Summarize the portfolio by asset type
    for asset in portfolio_data:
        asset_type = asset['type']
        asset_value = asset['quantity'] * asset['purchase_price']

        if asset_type in asset_summary:
            asset_summary[asset_type] += asset_value
        else:
            asset_summary[asset_type] = asset_value

    # Prepare data for bar chart
    labels = list(asset_summary.keys())  # Asset types (stocks, cryptocurrency, etc.)
    values = list(asset_summary.values())  # Asset values

    # Generate the bar chart
    plt.figure(figsize=(8, 6))
    plt.bar(labels, values, color=['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0','#ffb3e6'])

    plt.title('Portfolio Value by Asset Type', fontsize=16, fontweight='bold')
    plt.xlabel('Asset Types', fontsize=14, fontweight='bold')  # Bold x-axis label
    plt.ylabel('Total Value ($)', fontsize=14, fontweight='bold')  # Bold y-axis label

    # Save the bar chart image to the static folder
    chart_path = 'static/bar_chart.png'
    plt.savefig(chart_path)
    plt.close()

    return chart_path


@app.route('/')
def index():
    return render_template('index.html')  # This will render the login page


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user(email=email, password=password)

            # Store user data in Firestore (create a document for each user)
            user_ref = db.collection('users').document(email)
            user_ref.set({
                'email': email,
                'password': password  # Storing password as plain text for now (use hashing for security in production)
            })

            return render_template('signup_success.html')
        except Exception as e:
            return str(e)
    return render_template('signup.html')


    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Fetch user data from Firestore
            user_ref = db.collection('users').document(email)
            user_data = user_ref.get().to_dict()

            # Check if user exists and if the password matches
            if user_data and user_data['password'] == password:
                session['user'] = email
                return redirect(url_for('dashboard'))
            else:
                return "Invalid credentials, please try again."
        except Exception as e:
            return str(e)
    return render_template('login.html')


@app.route('/add_asset', methods=['POST'])
def add_asset():
    user_email = session.get('user')  # Get the logged-in user’s email
    if not user_email:
        return redirect(url_for('login'))

    # Get asset details from the form
    asset_type = request.form['type']  # Type of asset (Stock, Bond, etc.)
    symbol = request.form['symbol']
    quantity = int(request.form['quantity'])
    purchase_price = float(request.form['purchase_price'])

    # Store the asset in Firestore under the user's portfolio, including asset type
    portfolio_ref = db.collection('users').document(user_email).collection('portfolio')
    portfolio_ref.add({
        'type': asset_type,
        'symbol': symbol,
        'quantity': quantity,
        'purchase_price': purchase_price
    })

    return redirect(url_for('dashboard'))



@app.route('/dashboard')
def dashboard():
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))

    portfolio_ref = db.collection('users').document(user_email).collection('portfolio')
    assets = portfolio_ref.stream()

    portfolio_data = []
    for asset in assets:
        asset_data = asset.to_dict()
        asset_data['id'] = asset.id  # Add the asset ID to the asset data

        # Check if asset type is Stock or Cryptocurrency
        if asset_data['type'] == 'Stock':
            asset_data['current_price'] = get_stock_price(asset_data['symbol'])
        elif asset_data['type'] == 'Cryptocurrency':
            asset_data['current_price'] = get_crypto_price(asset_data['symbol'])
        else:
            asset_data['current_price'] = None  # For real estate or other assets

        # Calculate Profit/Loss and ROI if current price is available
        if asset_data['current_price'] is not None:
            asset_data['profit_loss'] = (asset_data['current_price'] - asset_data['purchase_price']) * asset_data['quantity']
            asset_data['roi'] = ((asset_data['current_price'] - asset_data['purchase_price']) / asset_data['purchase_price']) * 100
        else:
            asset_data['profit_loss'] = None
            asset_data['roi'] = None

        portfolio_data.append(asset_data)

    # Generate pie chart and bar chart
    pie_chart_path = plot_asset_value_pi_chart(portfolio_data)
    bar_chart_path = plot_asset_value_bar_chart(portfolio_data)

    return render_template('dashboard.html', portfolio_data=portfolio_data, pie_chart=pie_chart_path, bar_chart=bar_chart_path)



@app.route('/edit_asset/<asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))

    portfolio_ref = db.collection('users').document(user_email).collection('portfolio').document(asset_id)
    
    # Handle form submission
    if request.method == 'POST':
        new_quantity = float(request.form['quantity'])
        new_purchase_price = float(request.form['purchase_price'])

        # Update the asset in Firestore
        portfolio_ref.update({
            'quantity': new_quantity,
            'purchase_price': new_purchase_price,
        })

        return redirect(url_for('dashboard'))
    
    # For GET requests, load the asset data
    asset = portfolio_ref.get().to_dict()
    return render_template('edit_asset.html', asset=asset, asset_id=asset_id)



@app.route('/delete_asset/<asset_id>')
def delete_asset(asset_id):
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))

    portfolio_ref = db.collection('users').document(user_email).collection('portfolio').document(asset_id)
    
    # Delete the asset from Firestore
    portfolio_ref.delete()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    # Here, clear the session or remove authentication as needed
    session.clear()  # Clears all session data
    return redirect(url_for('signup'))  # Redirects to the signup page



if __name__ == '__main__':
    app.run(debug=True)
