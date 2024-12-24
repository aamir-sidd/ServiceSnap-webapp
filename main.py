from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///service_snap_db.db'
app.config['SECRET_KEY'] = 'service_snap'

db = SQLAlchemy(app)
app.app_context().push()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    user_type = db.Column(db.String(50), nullable=False)
    service_type = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)

    feedbacks = db.relationship('Feedback', backref='user', lazy=True)
    service_requests = db.relationship('ServiceRequest', backref='user', foreign_keys='ServiceRequest.user_id')
    service_professional_requests = db.relationship(
        'ServiceRequest', backref='service_professional', foreign_keys='ServiceRequest.service_professional_id'
    )

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)

    service_requests = db.relationship('ServiceRequest', backref='service', lazy=True, cascade='all, delete-orphan')

class Feedback(db.Model):
    __tablename__ = "feedbacks"
    id = db.Column(db.Integer, primary_key=True)
    service_professional_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)

class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_professional_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    date_of_request = db.Column(db.DateTime, default=datetime.utcnow)
    date_of_completion = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Pending')

# Login required decorator
def professional_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        elif session.get('user_type') != 'service professional':
            flash("Unauthorized access.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        elif session.get('user_type') != 'customer':
            flash("Unauthorized access.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        if session.get('user_type') != 'admin':
            flash("Unauthorized access.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        user_type = data.get('user_type')

        if user_type not in ['customer', 'service professional']:
            flash("Invalid user type.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(data['password'])
        new_user = User(
            name=data['name'],
            email=data['email'],
            password=hashed_password,
            address=data.get('address'),
            user_type=user_type,
            service_type=data.get('service_type') if user_type == 'service professional' else None,
            status='Inactive' if user_type == 'service professional' else 'Active',
            description=data.get('description')
        )
        db.session.add(new_user)
        db.session.commit()
        flash("User registered successfully.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        user = User.query.filter_by(email=data['email']).first()

        if user and check_password_hash(user.password, data['password']):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            if user.user_type == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.user_type == 'customer':
                if user.status != 'Active':
                    flash(f'Your account is {user.status}', "danger")
                    return redirect(url_for('login'))
                return redirect(url_for('customer_dashboard'))
            elif user.user_type == 'service professional':
                if user.status != 'Active':
                    flash(f'Your account is {user.status}', "danger")
                    return redirect(url_for('login'))
                return redirect(url_for('service_professional_dashboard'))
        
        flash("Invalid credentials.", "danger")
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/customer/dashboard')
@customer_required
def customer_dashboard():
    services = Service.query.all()
    service_requests = ServiceRequest.query.filter_by(user_id=session['user_id']).all()
    return render_template('customer_dashboard.html', services=services, service_requests=service_requests)
    
@app.route('/service_professional/dashboard')
@professional_required
def service_professional_dashboard():
    requested_requests = ServiceRequest.query.filter_by(service_professional_id=session['user_id'], status='Pending').all()
    accepted_requests = ServiceRequest.query.filter_by(service_professional_id=session['user_id'], status='Accepted').all()
    completed_requests = ServiceRequest.query.filter_by(service_professional_id=session['user_id'], status='Completed').all()
    return render_template('service_professional_dashboard.html', requested_requests=requested_requests, accepted_requests=accepted_requests, completed_requests=completed_requests)

@app.route('/create_service_request/<int:id>', methods=['GET', 'POST'])
@customer_required
def create_service_request(id):
    service = Service.query.get_or_404(id)
    if not service:
        flash("Service not found.", "danger")
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        service_professional_id = request.form.get('service_professional_id')
        completion_date = request.form.get('completion_date')

        new_request = ServiceRequest(service_id = id, user_id = session['user_id'], 
                                     service_professional_id = service_professional_id, 
                                     date_of_completion = datetime.strptime(completion_date, '%Y-%m-%d'))
        db.session.add(new_request)
        db.session.commit()
        flash("Service request created successfully.", "success")
        return redirect(url_for('customer_dashboard'))

    professionals = User.query.filter_by(user_type='service professional').all()

    return render_template('create_service_request.html', service = service, professionals = professionals)

@app.route('/edit_service_request/<int:id>', methods=['GET', 'POST'])
@customer_required
def edit_service_request(id):
    service_request = ServiceRequest.query.get_or_404(id)
    
    if not service_request:
        flash("Service Request not found.", "danger")
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        service_professional_id = request.form.get('service_professional_id')
        completion_date = request.form.get('completion_date')

        service_request.service_professional_id = service_professional_id
        service_request.date_of_completion = datetime.strptime(completion_date, '%Y-%m-%d')
        db.session.commit()
        flash("Service request updated successfully.", "success")
        return redirect(url_for('customer_dashboard'))

    professionals = User.query.filter_by(user_type='service professional').all()
    service_name = Service.query.get_or_404(service_request.service_id).name
    selected_professional = User.query.get_or_404(service_request.service_professional_id)
    return render_template(
        'edit_service_request.html', 
        service_request=service_request, 
        service_name=service_name,  
        selected_professional=selected_professional, 
        professionals=professionals,
        completion_date=service_request.date_of_completion.strftime('%Y-%m-%d')
    )

@app.route('/accept_service_request/<int:request_id>', methods=['POST'])
@professional_required
def accept_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)

    if service_request.status in ['Accepted', 'Completed']:
        flash("Service request already accepted or completed.", "danger")
        return redirect(url_for('service_professional_dashboard'))

    service_request.status = 'Accepted'
    db.session.commit()
    flash("Service request accepted successfully.", "success")
    return redirect(url_for('service_professional_dashboard'))

@app.route('/reject_service_request/<int:request_id>', methods=['POST'])
@professional_required
def reject_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)

    if service_request.status in ['Accepted', 'Completed']:
        flash("Service request already accepted or completed.", "danger")
        return redirect(url_for('service_professional_dashboard'))

    service_request.status = 'Rejected'
    db.session.commit()
    flash("Service request rejected successfully.", "success")
    return redirect(url_for('service_professional_dashboard'))

@app.route('/complete_service_request/<int:request_id>', methods=['POST'])
@professional_required
def complete_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)

    if service_request.status == 'Accepted':
        service_request.status = 'Completed'
        service_request.date_of_completion = datetime.utcnow()
        db.session.commit()
        flash("Service request completed successfully.", "success")
        return redirect(url_for('service_professional_dashboard'))

    flash("Service request not accepted.", "danger")
    return redirect(url_for('service_professional_dashboard'))

@app.route('/delete_service_request/<int:request_id>', methods=['POST'])
@customer_required
def delete_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    db.session.delete(service_request)
    db.session.commit()
    flash("Service request deleted successfully.", "success")
    return redirect(url_for('customer_dashboard'))

@app.route('/submit_feedback/<int:id>', methods=['GET', 'POST'])
@customer_required
def submit_feedback(id):
    professional = User.query.filter_by(id = id, user_type = "service professional").first()
    if not professional:
        flash("Not found.", "success")
        return redirect(url_for('customer_dashboard'))       
    if request.method == 'POST':
        data = request.form
        new_feedback = Feedback(service_professional_id=id, feedback_text=data['feedback_text'])
        db.session.add(new_feedback)
        db.session.commit()
        flash("Feedback submitted successfully.", "success")
        return redirect(url_for('customer_dashboard'))
    return render_template('feedback_form.html', professional = professional)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    services = Service.query.all()
    professionals = User.query.filter_by(user_type='service professional').all()
    customers = User.query.filter_by(user_type='customer').all()
    return render_template('admin_dashboard.html', services=services, professionals=professionals, customers=customers)

@app.route('/admin/service/create', methods=['GET', 'POST'])
@admin_required
def create_service():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        new_service = Service(name=name, description=description, price=price)
        db.session.add(new_service)
        db.session.commit()
        flash('Service created successfully!', "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('create_service.html')

@app.route('/admin/service/edit/<int:service_id>', methods=['GET', 'POST'])
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.price = request.form['price']
        db.session.commit()
        flash('Service updated successfully!', "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_service.html', service=service)

@app.route('/admin/service/delete/<int:service_id>', methods=['POST'])
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted successfully!', "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/approve_professional/<int:user_id>', methods=['POST'])
@admin_required
def approve_professional(user_id):
    professional = User.query.get_or_404(user_id)
    professional.status = 'Active'
    db.session.commit()
    flash("Professional approved successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/block_professional/<int:user_id>', methods=['POST'])
@admin_required
def block_professional(user_id):
    professional = User.query.get_or_404(user_id)
    professional.status = 'Blocked'
    db.session.commit()
    flash("Professional blocked successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/block_customer/<int:user_id>', methods=['POST'])
@admin_required
def block_customer(user_id):
    customer = User.query.get_or_404(user_id)
    customer.status = 'Blocked'
    db.session.commit()
    flash("Customer blocked successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/unblock_customer/<int:user_id>', methods=['POST'])
@admin_required
def unblock_customer(user_id):
    customer = User.query.get_or_404(user_id)
    customer.status = 'Active'
    db.session.commit()
    flash("Customer unblocked successfully.", "success")
    return redirect(url_for('admin_dashboard'))

def create_admin_user():
    with app.app_context():
        admin_user = User.query.filter_by(email='admin@gmail.com').first()

        if not admin_user:
            new_admin = User(
                name='Admin',
                email='admin@gmail.com',
                password=generate_password_hash('7894'),
                address='Admin Address',
                user_type='admin',
                service_type=None,
                status='active',
                description='Administrator account'
            )
            db.session.add(new_admin)
            db.session.commit()
            print("Admin user created.")


if __name__ == '__main__':
    db.create_all()
    create_admin_user()
    app.run(debug=True)
