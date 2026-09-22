import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction

from apps.tenants.models import Tenant
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch, ClassSession


COURSES_DATA = [
    # --- Young Innovators Learning Pathway ---
    {
        "name": "Young Innovators - Beginners Programme",
        "slug": "young-innovators-beginners-programme",
        "duration_months": 6,
        "duration_weeks": 24,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Foundational technology programme for children and young learners starting their coding journey.",
        "description": (
            "Our foundation programme for children and young learners beginning their technology journey. "
            "Students are introduced to HTML & CSS, JavaScript, Python, Generative AI, Problem Solving, "
            "Project Development, and Creativity & Innovation. Prepares learners for specialised pathways."
        ),
        "subjects": [
            ("HTML & CSS Fundamentals", "Building structural web pages with styling and layout design."),
            ("JavaScript for Young Innovators", "Interactive logic, events, and dynamic browser coding."),
            ("Python Core & Problem Solving", "Introduction to algorithmic thinking and computational logic."),
            ("Generative AI & Creative Tech", "Safe and practical exploration of AI tools for creative problem solving."),
            ("Practical Innovation Project Lab", "Guided hands-on capstone project synthesizing all foundational skills."),
        ],
    },
    {
        "name": "Data Analysis",
        "slug": "data-analysis",
        "duration_months": 4,
        "duration_weeks": 16,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Learn how to work with data, analyse information, discover patterns and communicate insights through practical projects.",
        "description": (
            "Specialised pathway for young and aspiring analysts. Learn how to extract, clean, manipulate, "
            "and visualize data. Master pattern recognition, statistical summaries, and communicate actionable insights."
        ),
        "subjects": [
            ("Data Processing & Spreadsheets", "Data cleaning, transformation, and spreadsheet analysis."),
            ("Python for Data Analysis", "Exploratory data analysis using Pandas, NumPy, and Jupyter."),
            ("Data Visualization & Dashboards", "Creating visual stories and charts using Matplotlib and Seaborn."),
            ("Capstone Data Storytelling Project", "End-to-end data project from raw dataset to executive insight presentation."),
        ],
    },
    {
        "name": "Python Programming",
        "slug": "python-programming",
        "duration_months": 3,
        "duration_weeks": 12,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Develop stronger programming skills using Python through increasingly challenging exercises and real-world projects.",
        "description": (
            "Develop strong algorithmic and software programming skills using Python. Covers core syntax, "
            "object-oriented architecture, modular code design, automation, and real-world project development."
        ),
        "subjects": [
            ("Python Fundamentals & Data Structures", "Lists, dictionaries, sets, tuples, and recursion."),
            ("Object-Oriented Programming (OOP)", "Classes, objects, inheritance, encapsulation, and polymorphism."),
            ("File Handling, APIs & Automation", "Interacting with system files, REST APIs, and automated scripting."),
            ("Real-World Python Application Project", "Building a functional terminal and desktop software application."),
        ],
    },
    {
        "name": "Robotics & Automation",
        "slug": "robotics-and-automation",
        "duration_months": 18,
        "duration_weeks": 72,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Long-term progressive pathway through electronics, programming, automation, sensors, robotics and practical innovation projects.",
        "description": (
            "Our premier 18-month long-term robotics pathway develops students progressively through "
            "electronics, microcontrollers, automation, sensor integration, mechanics, robotics engineering, "
            "and practical innovation projects designed to build real technology creators."
        ),
        "subjects": [
            ("Electronics & Circuit Prototyping", "Components, breadboards, circuit laws, and power distribution."),
            ("Microcontrollers & Embedded C/Python", "Programming Arduino, Raspberry Pi, and ESP32 controllers."),
            ("Sensors, Actuators & Motion", "Integrating ultrasonic, infrared, servo motors, and environmental sensors."),
            ("Automation, IoT & Wireless Systems", "Wireless communication, Bluetooth/WiFi modules, and smart devices."),
            ("Advanced Autonomous Robotics Capstone", "Designing, fabricating, and programming autonomous robotic systems."),
        ],
    },
    # --- Professional & Career-Shift Programmes ---
    {
        "name": "Full-Stack Web Development",
        "slug": "full-stack-web-development",
        "duration_months": 6,
        "duration_weeks": 24,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Learn both front-end and back-end development and progress towards building complete web applications.",
        "description": (
            "Designed for older students, graduates, professionals, entrepreneurs and adults transitioning into tech. "
            "Master full-cycle web engineering from responsive frontends to scalable backends, database architecture, "
            "REST APIs, authentication, and cloud deployment."
        ),
        "subjects": [
            ("Modern Frontend Engineering (HTML/CSS/JS)", "Semantic HTML5, CSS layout systems, modern JavaScript ES6+."),
            ("React Frontend Applications", "Component lifecycle, state hooks, routing, and modern frontend SPAs."),
            ("Backend Architecture with Python & Django", "MVC architecture, ORM, models, business logic, and security."),
            ("RESTful APIs & Database Management", "PostgreSQL, API design, token authentication, and integration."),
            ("Production Deployment & DevOps Basics", "Nginx, Gunicorn, Git workflows, and cloud server hosting."),
        ],
    },
    {
        "name": "Front-End Web Development",
        "slug": "front-end-web-development",
        "duration_months": 4,
        "duration_weeks": 16,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Learn to design and develop modern, responsive and interactive websites and user interfaces.",
        "description": (
            "Focused career program in UI engineering. Learn how to transform designs into responsive, "
            "accessible, high-performance web interfaces using modern frameworks, responsive styling, and dynamic animations."
        ),
        "subjects": [
            ("UI/UX Principles & Responsive Design", "Figma to code translation, modern CSS frameworks, and design tokens."),
            ("Advanced JavaScript & Web APIs", "DOM manipulation, asynchronous JavaScript, Fetch API, and storage."),
            ("React & Component Architecture", "State management, reusable component libraries, and client routing."),
            ("Portfolio Showcase & Production Project", "Polishing production portfolio websites for developer job readiness."),
        ],
    },
    {
        "name": "Cloud Engineering & DevOps",
        "slug": "cloud-engineering-devops",
        "duration_months": 8,
        "duration_weeks": 32,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Build practical skills in cloud infrastructure, deployment, servers, networking, DevOps fundamentals and modern cloud technologies.",
        "description": (
            "Comprehensive cloud engineering curriculum covering Linux administration, virtual networking, "
            "AWS/Azure architecture, containerization with Docker, CI/CD automated pipelines, and infrastructure as code."
        ),
        "subjects": [
            ("Linux Systems Administration & Bash", "Command line mastery, file systems, permissions, process management."),
            ("Networking & Cloud Security Essentials", "TCP/IP, DNS, routing, firewalls, and SSL/TLS infrastructure."),
            ("Cloud Architecture (AWS / Multi-Cloud)", "Compute (EC2), Object Storage (S3), IAM, VPCs, and Load Balancing."),
            ("Docker & Container Orchestration", "Building images, multi-stage builds, Docker Compose, and Kubernetes basics."),
            ("CI/CD Automation & Infrastructure as Code", "GitHub Actions, Terraform provisioning, and monitoring pipelines."),
        ],
    },
    {
        "name": "Ethical Hacking & Cybersecurity",
        "slug": "ethical-hacking-cybersecurity",
        "duration_months": 4,
        "duration_weeks": 16,
        "monthly_fee": Decimal("35000.00"),
        "short_description": "Learn cybersecurity fundamentals, system and network security, vulnerability assessment and ethical security testing.",
        "description": (
            "Practical cybersecurity training covering ethical hacking methodologies, defense strategies, "
            "vulnerability assessment, penetration testing tools, network packet analysis, and security compliance in legal sandboxes."
        ),
        "subjects": [
            ("Cybersecurity Fundamentals & Threat Modeling", "Security triad (CIA), threat vectors, authentication and access controls."),
            ("Network Defense & Packet Analysis", "Wireshark packet inspection, port scanning, firewalls, and IDS/IPS."),
            ("Vulnerability Assessment & Web Security", "OWASP Top 10 vulnerabilities, SQL injection, XSS, and scanner tools."),
            ("Ethical Penetration Testing & Incident Response", "Hands-on penetration testing in authorized virtual lab environments."),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed CodeCamp Innovation Hub programmes, subjects, and batch schedules for the upcoming session."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-slug",
            type=str,
            default="lagos-hq",
            help="Tenant slug to associate courses with (default: lagos-hq)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default=None,
            help="Cohort start date in YYYY-MM-DD format (default: next Monday)",
        )

    def handle(self, *args, **options):
        tenant_slug = options["tenant_slug"]
        start_date_str = options["start_date"]

        # 1. Resolve Tenant
        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if not tenant:
            tenant = Tenant.objects.filter(is_default=True).first()
        if not tenant:
            tenant = Tenant.objects.create(
                name="CodeCamp Innovation Hub",
                slug="lagos-hq",
                subdomain="lagos",
                subscription_tier="enterprise",
                max_students=2000,
                is_default=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Created Tenant: {tenant.name}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Using Tenant: {tenant.name} ({tenant.slug})"))

        # 2. Determine default start date (Next Monday)
        today = timezone.localdate()
        if start_date_str:
            start_date = datetime.date.fromisoformat(start_date_str)
        else:
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            start_date = today + datetime.timedelta(days=days_ahead)

        self.stdout.write(self.style.NOTICE(f"Cohort Start Date: {start_date}"))

        with transaction.atomic():
            courses_created = 0
            courses_updated = 0
            subjects_count = 0
            batches_count = 0

            for c_data in COURSES_DATA:
                total_fee = c_data["monthly_fee"] * c_data["duration_months"]
                duration_weeks = c_data["duration_weeks"]
                end_date = start_date + datetime.timedelta(weeks=duration_weeks)

                course, created = Course.objects.update_or_create(
                    tenant=tenant,
                    slug=c_data["slug"],
                    defaults={
                        "name": c_data["name"],
                        "short_description": c_data["short_description"],
                        "description": c_data["description"],
                        "duration_weeks": duration_weeks,
                        "fee": total_fee,
                        "is_published": True,
                    },
                )

                if created:
                    courses_created += 1
                    self.stdout.write(self.style.SUCCESS(f"[CREATED] Course: {course.name} ({c_data['duration_months']} Mo / NGN {c_data['monthly_fee']:,} per mo)"))
                else:
                    courses_updated += 1
                    self.stdout.write(self.style.SUCCESS(f"[UPDATED] Course: {course.name}"))

                # Create Subjects
                for subj_name, subj_desc in c_data["subjects"]:
                    subject, _ = Subject.objects.get_or_create(
                        course=course,
                        name=subj_name,
                        defaults={"description": subj_desc},
                    )
                    subjects_count += 1

                # Create 3 Standard Batches:
                # 1. Weekday Onsite (10:00 AM - 1:00 PM Mon/Wed/Fri)
                b_weekday, _ = Batch.objects.get_or_create(
                    tenant=tenant,
                    course=course,
                    name=f"{course.name} - Weekday Cohort (10am-1pm)",
                    defaults={
                        "mode": "onsite",
                        "batch_type": "weekdays",
                        "session_period": "morning",
                        "days_pattern": "mon_wed_fri",
                        "start_date": start_date,
                        "end_date": end_date,
                        "duration_weeks": duration_weeks,
                        "max_students": 25,
                        "is_published": True,
                    },
                )
                batches_count += 1

                # 2. Weekend Onsite (Fri 4pm-6pm & Sat 9am-3pm)
                b_weekend, _ = Batch.objects.get_or_create(
                    tenant=tenant,
                    course=course,
                    name=f"{course.name} - Weekend Cohort (Fri/Sat)",
                    defaults={
                        "mode": "onsite",
                        "batch_type": "weekends",
                        "session_period": "morning",
                        "days_pattern": "fri_sat",
                        "start_date": start_date,
                        "end_date": end_date,
                        "duration_weeks": duration_weeks,
                        "max_students": 25,
                        "is_published": True,
                    },
                )
                batches_count += 1

                # 3. Online Virtual Cohort (Flexible Instructor-Led)
                b_online, _ = Batch.objects.get_or_create(
                    tenant=tenant,
                    course=course,
                    name=f"{course.name} - Online Virtual Cohort",
                    defaults={
                        "mode": "online",
                        "batch_type": "weekdays",
                        "session_period": "morning",
                        "days_pattern": "mon_wed_fri",
                        "start_date": start_date,
                        "end_date": end_date,
                        "duration_weeks": duration_weeks,
                        "max_students": 100,
                        "is_published": True,
                    },
                )
                batches_count += 1

                # Add Sessions for Weekday Batch
                first_subject = course.subjects.first()
                if first_subject:
                    for day in ["monday", "wednesday", "friday"]:
                        ClassSession.objects.get_or_create(
                            batch=b_weekday,
                            day=day,
                            time_period="morning",
                            defaults={
                                "subject": first_subject,
                                "duration_hours": 3,
                                "start_time": datetime.time(10, 0),
                                "end_time": datetime.time(13, 0),
                            },
                        )

                    # Add Sessions for Weekend Batch (Fri 4-6pm, Sat 9am-3pm)
                    ClassSession.objects.get_or_create(
                        batch=b_weekend,
                        day="friday",
                        time_period="afternoon",
                        defaults={
                            "subject": first_subject,
                            "duration_hours": 2,
                            "start_time": datetime.time(16, 0),
                            "end_time": datetime.time(18, 0),
                        },
                    )
                    ClassSession.objects.get_or_create(
                        batch=b_weekend,
                        day="saturday",
                        time_period="morning",
                        defaults={
                            "subject": first_subject,
                            "duration_hours": 6,
                            "start_time": datetime.time(9, 0),
                            "end_time": datetime.time(15, 0),
                        },
                    )

            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("CODECAMP INNOVATION HUB PROGRAMME SEED COMPLETE"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(f" - Courses Created:  {courses_created}")
            self.stdout.write(f" - Courses Updated:  {courses_updated}")
            self.stdout.write(f" - Subjects Loaded:  {subjects_count}")
            self.stdout.write(f" - Batches Assigned: {batches_count}")
            self.stdout.write(f" - All courses priced at NGN 35,000/month with Weekday, Weekend & Online cohorts.")
            self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))
