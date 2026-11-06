import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

TIME_SLOTS = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]


def execute_sql(query: str, params: tuple = (), fetch: bool = False):
    conn = sqlite3.connect("restaurant.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    result = [dict(row) for row in cursor.fetchall()] if fetch else None
    conn.close()
    return result


def setup_database():
    # Создание таблиц
    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            name TEXT
        )
    """
    )

    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY,
            seats INTEGER,
            zone TEXT
        )
    """
    )

    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            table_id INTEGER,
            date TEXT,
            time TEXT
        )
    """
    )

    # Гарантированное наполнение ровно 10 столиков
    for i in range(1, 11):
        seats = 2 if i <= 3 else (4 if i <= 8 else 6)
        zone = "У окна" if i <= 3 else ("Зал" if i <= 8 else "VIP")
        execute_sql(
            "INSERT OR IGNORE INTO tables (id, seats, zone) VALUES (?, ?, ?)",
            (i, seats, zone),
        )


setup_database()


@app.get("/", response_class=HTMLResponse)
def get_home_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/register")
async def register_user(request: Request):
    data = await request.json()
    phone = data.get("phone")
    name = data.get("name", "Гость")
    execute_sql(
        "INSERT OR IGNORE INTO users (phone, name) VALUES (?, ?)", (phone, name)
    )
    return {"status": "ok"}


@app.get("/api/tables")
def get_tables_list(date: str):
    tables = execute_sql("SELECT * FROM tables ORDER BY id", fetch=True)
    bookings = execute_sql(
        "SELECT table_id, time FROM bookings WHERE date = ?", (date,), fetch=True
    )
    for table in tables:
        table["booked_times"] = [
            b["time"] for b in bookings if b["table_id"] == table["id"]
        ]
        table["all_slots"] = TIME_SLOTS
    return tables


@app.post("/api/book")
async def create_booking(request: Request):
    data = await request.json()
    phone = data.get("phone")
    table_id = data.get("table_id")
    date = data.get("date")
    time = data.get("time")

    check = execute_sql(
        "SELECT id FROM bookings WHERE table_id = ? AND date = ? AND time = ?",
        (table_id, date, time),
        fetch=True,
    )
    if check:
        return {"status": "error", "message": "Этот слот времени уже занят!"}

    execute_sql(
        "INSERT INTO bookings (phone, table_id, date, time) VALUES (?, ?, ?, ?)",
        (phone, table_id, date, time),
    )
    return {"status": "ok"}


@app.get("/api/my-bookings")
def get_user_bookings(phone: str):
    return execute_sql(
        """
        SELECT b.id, b.date, b.time, t.id as table_id, t.zone, t.seats
        FROM bookings b
        JOIN tables t ON b.table_id = t.id
        WHERE b.phone = ?
        ORDER BY b.date, b.time
    """,
        (phone,),
        fetch=True,
    )


@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int):
    execute_sql("DELETE FROM bookings WHERE id = ?", (booking_id,))
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)