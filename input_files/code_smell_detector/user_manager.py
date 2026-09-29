import smtplib
import sqlite3


class UserManager:
    def __init__(self):
        self.db = sqlite3.connect("users.db")
        self.smtp = smtplib.SMTP("smtp.example.com", 587)
        self.cache = {}

    def add_user(self, name, email, age, role, country, newsletter):
        self.db.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, age, role, country, newsletter),
        )
        self.db.commit()

    def get_user(self, email):
        if email in self.cache:
            return self.cache[email]
        row = self.db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            self.cache[email] = row
            return row
        return False

    def send_welcome_email(self, email):
        self.smtp.sendmail("noreply@example.com", email, "Welcome!")

    def generate_monthly_report(self):
        rows = self.db.execute("SELECT * FROM users").fetchall()
        return "\n".join(f"{r[0]},{r[1]},{r[4]}" for r in rows)

    def resize_avatar(self, image_bytes, width, height):
        return image_bytes[: width * height]

    def format_address(self, user):
        return f"{user[0]}\n{user[5]['street']}\n{user[5]['city']} {user[5]['zip']}"
