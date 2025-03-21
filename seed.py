import random
from app import app, db
from models import User, Department, Service
from werkzeug.security import generate_password_hash

# Department names
departments = [
    "Records Management Department",
    "Telephone Section Department",
    "Transport Section Department",
    "Central Planning and Project Monitoring Department",
    "Finance Department",
    "Accounts Section",
    "Human Resource Management and Development Department",
    "ICT Department",
    "Internal Audit Department",
    "Public Communication Department",
    "Youth and Gender",
    "Supply Chain Management Department",
    "Marriages",
    "Societies",
    "Coat of Arms",
    "Planning Department"
]

# Sample services for each department
services_dict = {
    "Records Management Department": "Document Filing",
    "Telephone Section": "Call Management",
    "Transport Section": "Fleet Management",
    "Central Planning and Project Monitoring Department": "Project Evaluation",
    "Finance Department": "Budgeting",
    "Accounts Department": "Payroll Processing",
    "Human Resource Management and Development Department": "Recruitment",
    "ICT Department": "Network Security",
    "Internal Audit Department": "Risk Assessment",
    "Public Communication Department": "Media Relations",
    "Youth and Gender": "Youth Empowerment Programs",
    "Supply Chain Management Department": "Procurement Planning",
    "Marriages": "Marriage Registration",
    "Societies": "NGO Registration",
    "Coat of Arms": "Emblem Design",
    "Planning Department": "Strategic Development"
}

# Create departments
with app.app_context():
    db.drop_all()
    db.create_all()
    
    department_instances = {}
    for dept_name in departments:
        department = Department(name=dept_name)
        db.session.add(department)
        department_instances[dept_name] = department
    
    db.session.commit()

    # Create users (one per department + Head of Planning)
    users = []
    for dept in department_instances.values():
        role = "department_user"
        if dept.name == "Planning Department":
            role = "head_of_planning"
        
        user = User(
            first_name=f"{dept.name.split()[0]}User",
            last_name="Doe",
            email=f"{dept.name.lower().replace(' ', '_')}@ag.go.ke",
            password=generate_password_hash("password123"),
            department_id=dept.id,
            role=role
        )
        users.append(user)

    db.session.add_all(users)
    db.session.commit()

    # Create only one service per department for a given month & year
    for dept_name, service_name in services_dict.items():
        department = Department.query.filter_by(name=dept_name).first()
        if department:
            service_instance = Service(
                department_id=department.id,
                month=1,  # Fixed month to avoid duplicate months
                year=2025,  # Fixed year to avoid conflicts
                service_count=random.randint(10, 100)
            )
            db.session.add(service_instance)

    db.session.commit()
    print("Database seeded successfully!")
