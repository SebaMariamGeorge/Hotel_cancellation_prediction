import random
from datetime import datetime

from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
import pickle

app = Flask(__name__)
app.secret_key = "hotel_secret_key"

# =====================================
# MYSQL CONFIGURATION
# =====================================

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hotel_ml'

mysql = MySQL(app)
model = pickle.load(
    open("model.pkl", "rb")
)

columns = pickle.load(
    open("columns.pkl", "rb")
)

# =====================================
# WELCOME PAGE
# =====================================

@app.route('/')
def welcome():
    return render_template('welcome.html')


# =====================================
# USER PORTAL
# =====================================

@app.route('/user-portal')
def user_portal():
    return render_template('user_portal.html')


# =====================================
# STAFF PORTAL
# =====================================

@app.route('/staff-portal')
def staff_portal():
    return render_template('staff_portal.html')


# =====================================
# USER SIGNUP
# =====================================

@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        existing_user = cur.fetchone()

        if existing_user:

            cur.close()

            return """
            <script>
            alert('Account already exists. Please login.');
            window.location='/login';
            </script>
            """

        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]

        user_id = f"U{1000 + count + 1}"

        cur.execute("""
        INSERT INTO users(user_id,name,email,password)
        VALUES(%s,%s,%s,%s)
        """, (user_id, name, email, password))

        mysql.connection.commit()
        cur.close()

        return redirect('/login')

    return render_template('signup.html')


# =====================================
# USER LOGIN
# =====================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cur.fetchone()

        # User does not exist
        if not user:

            cur.close()

            return """
            <script>
            alert('User ID / Email does not exist');
            window.location='/login';
            </script>
            """

        # Wrong password
        if user[4] != password:

            cur.close()

            return """
            <script>
            alert('Incorrect Password');
            window.location='/login';
            </script>
            """

        # Save login session
        session["email"] = email

        # Check whether the user already has a booking
        cur.execute("""
        SELECT *
        FROM bookings
        WHERE email=%s
        ORDER BY booking_id DESC
        """, (email,))

        booking = cur.fetchone()


        if booking:
            return redirect("/my-booking")

        return redirect("/booking")

    return render_template('login.html')
# =====================================
# STAFF LOGIN
# =====================================

@app.route('/staff-login', methods=['GET', 'POST'])
def staff_login():

    if request.method == 'POST':

        staff_name = request.form['staff_name']
        password = request.form['password']

        expected_password = staff_name.lower() + "1234"

        if password == expected_password:
            return redirect('/dashboard')

        return """
        <script>
        alert('Incorrect Staff Password');
        window.location='/staff-login';
        </script>
        """

    return render_template('staff_login.html')


# =====================================
# BOOKING PAGE
# =====================================

@app.route('/booking')
def booking():

    today = datetime.today().strftime("%Y-%m-%d")

    return render_template(
        'booking.html',
        today=today
    )

# =====================================
# MY BOOKING
# =====================================

@app.route("/my-booking")
def my_booking():

    if "email" not in session:
        return redirect("/login")

    email = session["email"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT
        guest_name,
        room_number,
        checkin_date,
        checkout_date,
        adults,
        children_under3,
        children_3_10,
        children_above10
    FROM bookings
    WHERE email=%s
    ORDER BY booking_id DESC
    """, (email,))

    bookings = cur.fetchall()

    cur.close()

    if not bookings:
        return redirect("/booking")

    return render_template(
        "my_booking.html",
        bookings=bookings
    )

# =====================================
# STAFF DASHBOARD
# =====================================

@app.route('/dashboard')
def dashboard():

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT
        booking_id,
        guest_name,
        room_number,
        cancellation_probability,
        overbooking_probability
    FROM bookings
    ORDER BY booking_id DESC
    """)

    bookings = cur.fetchall()

    cur.close()

    return render_template(
        "dashboard.html",
        bookings=bookings
    )
# =====================================
# SAVE BOOKING
# =====================================

@app.route('/save-booking', methods=['POST'])
def save_booking():
   
    guest_name = request.form['guest_name']
    phone = request.form['phone']
    email = session["email"]
    

    checkin_date = request.form['checkin_date']
    checkout_date = request.form['checkout_date']
    today = datetime.today().date()

    checkin = datetime.strptime(
       checkin_date,
       "%Y-%m-%d"
    ).date()

    checkout = datetime.strptime(
       checkout_date,
       "%Y-%m-%d"
    ).date()

    if checkin < today:

       return """
       <script>
       alert('Check-in date cannot be in the past');
       window.history.back();
       </script>
       """

    adults = request.form.get(
    'adults',
    '0'
    ) or '0'

    child_under3 = request.form.get(
    'children_under3',
    '0'
    ) or '0'

    child_3_10 = request.form.get(
    'children_3_10',
    '0'
    ) or '0'

    child_above10 = request.form.get(
    'children_above10',
    '0'
    ) or '0'

    pet_category = request.form['pet_category']

    pet_type = request.form.get(
        'pet_type',
        ''
    )

    room_number = random.randint(101, 399)

    # ==========================
    # ML PREDICTION
    # ==========================

    lead_time = 30
    adr = 120
    previous_cancellations = 0
    booking_changes = 0

    data = [0] * len(columns)

    if "lead_time" in columns:
        data[columns.index("lead_time")] = lead_time

    if "adr" in columns:
        data[columns.index("adr")] = adr

    if "previous_cancellations" in columns:
        data[columns.index("previous_cancellations")] = previous_cancellations

    if "booking_changes" in columns:
        data[columns.index("booking_changes")] = booking_changes

    cancel_probability = round(
        model.predict_proba([data])[0][1] * 100,
        2
    )

    if cancel_probability >= 80:
        overbooking_probability = 80

    elif cancel_probability >= 60:
        overbooking_probability = 50

    else:
        overbooking_probability = 10

    # ==========================
    # CALCULATE STAY DAYS
    # ==========================

    d1 = datetime.strptime(
        checkin_date,
        "%Y-%m-%d"
    )

    d2 = datetime.strptime(
        checkout_date,
        "%Y-%m-%d"
    )

    days = (d2 - d1).days

    if days <= 0:

       return """
       <script>
       alert('Checkout date must be after Check-in date');
       window.history.back();
       </script>
       """

    # ==========================
    # SAVE TO MYSQL
    # ==========================

    cur = mysql.connection.cursor()

    cur = mysql.connection.cursor()

    cur.execute("""
    cur.execute("SELECT MAX(room_number) FROM bookings")
    last_room = cur.fetchone()[0]

    if last_room is None:
         room_number = 201

    else:
         room_number = int(last_room) + 1
    INSERT INTO bookings
    (
        email,
        guest_name,
        phone,
        checkin_date,
        checkout_date,
        adults,
        children_under3,
        children_3_10,
        children_above10,
        pet_category,
        pet_type,
        lead_time,
        adr,
        previous_cancellations,
        booking_changes,
        room_number,
        cancellation_probability,
        overbooking_probability
    )
    VALUES
    (
        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
        %s,%s,%s,%s,%s,%s,%s,%s
    )
    """,
    (
        email,
        guest_name,
        phone,
        checkin_date,
        checkout_date,
        adults,
        child_under3,
        child_3_10,
        child_above10,
        pet_category,
        pet_type,
        lead_time,
        adr,
        previous_cancellations,
        booking_changes,
        room_number,
        cancel_probability,
        overbooking_probability
    ))

    mysql.connection.commit()

    cur.close()

    return render_template(
        "success.html",
        guest_name=guest_name,
        room_number=room_number,
        checkin=checkin_date,
        checkout=checkout_date,
        days=days,
        adults=adults,
        total_children=
            int(child_under3)
            + int(child_3_10)
            + int(child_above10)
    )

# =====================================
# RUN APP
# =====================================

if __name__ == "__main__":
    app.run(debug=True)