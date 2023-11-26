from flask import Flask, render_template, request, redirect, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
import string
import random
import qrcode
from flask import abort
import os

app = Flask(__name__, template_folder="templates")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    long_url = db.Column(db.String(255), nullable=False)
    short_code = db.Column(db.String(6), unique=True, nullable=False)
    qr_code = db.Column(db.LargeBinary, nullable=True)

def init_db():
    with app.app_context():
        db.create_all()

# Initialize the database within the application context
init_db()

def generate_short_code():
    characters = string.ascii_letters + string.digits
    short_code = ''.join(random.choice(characters) for _ in range(6))
    return short_code.upper()

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    return img.tobytes()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorten', methods=['POST'])
def shorten_url():
    try:
        long_url = request.form.get('long_url')
        customize_code = request.form.get('customize_code')

        # Check if the custom code already exists
        if customize_code and URL.query.filter_by(short_code=customize_code.upper()).first():
            return jsonify({"error": "Custom code already exists."}), 400

        short_code = customize_code.upper() if customize_code else generate_short_code()

        # Save to the database
        new_url = URL(long_url=long_url, short_code=short_code)
        db.session.add(new_url)
        db.session.commit()

        # Generate QR code
        qr_code = generate_qr_code(long_url)
        new_url.qr_code = qr_code
        db.session.commit()

        return jsonify({"shortened_url": short_code, "link": f"{request.host_url}{short_code}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/qrcode')
def generate_qr_code_route():
    short_code = request.args.get('data')
    if short_code:
        url_entry = URL.query.filter_by(short_code=short_code).first()
        if url_entry:
            # Generate QR code
            qr_code = generate_qr_code_bytes(url_entry.long_url)

            # Specify the directory for QR codes
            qr_code_dir = "qrcodes"
            os.makedirs(qr_code_dir, exist_ok=True)  # Create directory if not exists

            # Save the QR code as a file
            qr_code_path = os.path.join(qr_code_dir, f"{short_code}.png")
            with open(qr_code_path, 'wb') as f:
                f.write(qr_code)

            # Return the path or URL to the QR code
            return jsonify({"qr_code_url": f"/{qr_code_path}"})
    
    return jsonify({"error": "Invalid short code"}), 404


def generate_qr_code_bytes(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    return img.tobytes()




@app.route('/list', methods=['GET'])
def list_urls():
    urls = URL.query.all()
    url_list = [{"short_code": url.short_code, "long_url": url.long_url} for url in urls]
    return jsonify(url_list)

@app.route('/test', methods=['GET'])
def test_short_url():
    short_code = request.args.get('short_code')
    if short_code:
        # Check if the short code exists in the database
        url = URL.query.filter_by(short_code=short_code).first()
        if url:
            return jsonify({"success": True, "long_url": url.long_url})
        else:
            return jsonify({"success": False, "error": "Short code not found"}), 404
    else:
        return jsonify({"success": False, "error": "Missing short code parameter"}), 400

@app.route('/<short_code>', methods=['GET'])
def redirect_to_original_url(short_code):
    # Find the URL in the database based on the short code
    url_entry = URL.query.filter_by(short_code=short_code.upper()).first()

    if url_entry:
        # Redirect to the original URL
        return redirect(url_entry.long_url)
    else:
        # If the short code doesn't exist, return a 404 error
        abort(404)


if __name__ == "__main__":
    try:
        app.run(debug=True)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
