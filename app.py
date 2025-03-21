from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, current_user,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
from models import db, User, Department, Service

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://report_managment_system_user:ZmmWAP90xkfNxVGB0PoDHKo6F8jsIKpn@dpg-cvelp67noe9s73eplb4g-a.oregon-postgres.render.com/report_managment_system'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-jwt-secret-key'

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
CORS(app, origins=["http://127.0.0.1:5173"], supports_credentials=True)

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.get(identity)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    required = ['first_name', 'last_name', 'email', 'password', 'department_id']
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        password=generate_password_hash(data['password']),
        department_id=data['department_id'],
        role=data.get('role', 'department_user')
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    
    if user and check_password_hash(user.password, data.get('password')):
        access_token = create_access_token(identity=user)
        return jsonify({
            "access_token": access_token,
            "role": user.role,
            "department_id": user.department_id,
            "department": user.department.name
        }), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/services', methods=['POST'])
@jwt_required()
def submit_service():
    if current_user.role != 'department_user':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    if not all(k in data for k in ['month', 'year', 'count']):
        return jsonify({"error": "Missing fields"}), 400

    try:
        month = int(data['month'])
        year = int(data['year'])
        count = int(data['count'])
        if not (1 <= month <= 12) or count < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Invalid input"}), 400

    # Get the current month and year
    current_month = datetime.now().month
    current_year = datetime.now().year

    # Validate that the month and year are not in the future
    if year > current_year or (year == current_year and month > current_month):
        return jsonify({"error": "Cannot submit reports for future months"}), 400

    service = Service.query.filter_by(
        department_id=current_user.department_id,
        month=month,
        year=year
    ).first()

    if service:
        service.service_count = count
    else:
        service = Service(
            department_id=current_user.department_id,
            month=month,
            year=year,
            service_count=count
        )
        db.session.add(service)
    
    db.session.commit()
    return jsonify({"message": "Record updated"}), 200

@app.route("/services/history", methods=["GET"])
@jwt_required()
def get_history():
    if current_user.role != 'department_user':
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get query parameters for filtering and pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)

        # Base query for the user's department
        query = Service.query.filter_by(department_id=current_user.department_id)

        # Apply filters if provided
        if year:
            query = query.filter_by(year=year)
        if month:
            query = query.filter_by(month=month)

        # Apply pagination
        paginated_records = query.order_by(
            Service.year.desc(), 
            Service.month.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        # Format the response
        history_data = [{
            "id": record.id,
            "month": record.month,
            "year": record.year,
            "service_count": record.service_count,
            "department": record.department.name
        } for record in paginated_records.items]

        # Include pagination metadata in the response
        return jsonify({
            "history": history_data,
            "pagination": {
                "page": paginated_records.page,
                "per_page": paginated_records.per_page,
                "total_pages": paginated_records.pages,
                "total_records": paginated_records.total,
                "has_next": paginated_records.has_next,
                "has_prev": paginated_records.has_prev
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reports", methods=["GET"])
@jwt_required()
def get_reports():
    if current_user.role != 'head_of_planning':
        return jsonify({"error": "Unauthorized"}), 403

    try:
        year = request.args.get('year', type=int)
        if not year:
            return jsonify({"error": "Year is required"}), 400

        # Get the current month and year
        current_month = datetime.now().month
        current_year = datetime.now().year

        # Get all departments
        departments = Department.query.all()
        months = list(range(1, 13))  # 1 to 12 for months

        # Prepare the report data
        report_data = []
        for department in departments:
            department_row = {"department": department.name}
            for month in months:
                # Check if the month is in the future
                if year > current_year or (year == current_year and month > current_month):
                    department_row[str(month)] = None  # Blank for future months
                else:
                    # Check if the user has submitted a report for this month
                    service = Service.query.filter_by(
                        department_id=department.id,
                        year=year,
                        month=month
                    ).first()
                    department_row[str(month)] = service.service_count if service else 0  # 0 for missing reports
            report_data.append(department_row)

        return jsonify({
            "year": year,
            "report": report_data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/reports/export', methods=['GET'])
@jwt_required()
def export_reports():
    if current_user.role != 'planning_head':
        return jsonify({"error": "Unauthorized"}), 403

    services = Service.query.all()
    data = [{
        'Department': s.department.name,
        'Month': s.month,
        'Year': s.year,
        'Service Count': s.service_count
    } for s in services]

    df = pd.DataFrame(data)
    export_format = request.args.get('format', 'csv').lower()
    
    try:
        if export_format == 'csv':
            df.to_csv('reports.csv', index=False)
        elif export_format == 'excel':
            df.to_excel('reports.xlsx', index=False)
        else:
            raise ValueError
    except:
        return jsonify({"error": "Invalid format"}), 400

    return jsonify({"message": f"Exported as {export_format}"}), 200


@app.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    if current_user.role not in ['department_user', 'planning_head']:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "department": user.department.name
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/profile/update", methods=["PUT"])
@jwt_required()
def update_profile():
    if current_user.role not in ['department_user', 'planning_head']:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update first name and last name
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]

        # Update email (if provided and unique)
        if "email" in data:
            if data["email"] != user.email and User.query.filter_by(email=data["email"]).first():
                return jsonify({"error": "Email already exists"}), 409
            user.email = data["email"]

        # Update password (if provided)
        if "password" in data:
            user.password = generate_password_hash(data["password"])

        db.session.commit()
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500    

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)