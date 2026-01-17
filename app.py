from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, session, url_for
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
import os
import uuid

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Secret key for sessions (use environment variable in production)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Admin credentials (use environment variables in production)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Configuration
DATABASE = 'calendar_events.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'jfif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with the events and images tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            event_date DATE DEFAULT '',
            event_time TEXT DEFAULT '',
            location TEXT DEFAULT '',
            category TEXT DEFAULT 'general' CHECK(category IN ('general', 'academic', 'social', 'spiritual', 'career')),
            author TEXT DEFAULT '',
            author_initials TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    ''')
    
    # Insert sample data if table is empty
    cursor.execute('SELECT COUNT(*) FROM events')
    if cursor.fetchone()[0] == 0:
        sample_events = [
            ('Spring Devotional', 
             'Join us for an inspiring devotional with guest speaker Elder Johnson. Light refreshments will be served after the event.',
             '2026-02-15', '10:00 AM', 'Main Auditorium', 'spiritual', 'Campus Ministry', 'CM'),
            ('Career Fair 2026',
             'Connect with top employers from various industries. Bring your resume and dress professionally. Over 50 companies attending!',
             '2026-02-20', '9:00 AM - 4:00 PM', 'Student Center', 'career', 'Career Services', 'CS'),
            ('Study Group Meetup',
             'Weekly study group for PathwayConnect students. All subjects welcome. Tutors available for math and writing assistance.',
             '2026-01-25', '6:00 PM', 'Library Room 204', 'academic', 'Academic Support', 'AS'),
            ('Winter Social Night',
             'Fun evening of games, music, and fellowship. Hot chocolate bar and snacks provided. Bring a friend!',
             '2026-02-01', '7:00 PM', 'Recreation Hall', 'social', 'Student Council', 'SC'),
            ('Registration Deadline Reminder',
             'Last day to register for Spring semester courses without late fees. Check your student portal for available classes.',
             '2026-01-20', '11:59 PM', 'Online', 'academic', 'Registrar Office', 'RO'),
        ]
        cursor.executemany('''
            INSERT INTO events (title, description, event_date, event_time, location, category, author, author_initials)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_events)
    
    conn.commit()
    conn.close()


# ==================== AUTH HELPERS ====================

def login_required(f):
    """Decorator to require admin login for page routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """Decorator to require admin login for API routes (returns 401)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==================== PAGE ROUTES ====================

@app.route('/')
def index():
    """Root route - redirect to display page."""
    return render_template('display.html')


@app.route('/display')
def display_page():
    """Public display page - Infinite autoplay image slider."""
    return render_template('display.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login page for admin access."""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_page'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_page'))
        else:
            error = 'Invalid username or password'
    
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Log out the admin user."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('login_page'))


@app.route('/admin')
@login_required
def admin_page():
    """Admin dashboard for managing events."""
    return render_template('admin.html')


# Serve templates directly as well (for compatibility)
@app.route('/templates/<path:filename>')
def serve_template(filename):
    """Serve template files directly."""
    return render_template(filename)


# ==================== FILE ROUTES ====================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==================== API ROUTES ====================

@app.route('/api/events', methods=['GET'])
def get_events():
    """Get all events with their images, ordered by date."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM events 
        ORDER BY event_date ASC, created_at DESC
    ''')
    events = []
    for row in cursor.fetchall():
        event = dict(row)
        # Get images for this event
        cursor.execute('SELECT * FROM event_images WHERE event_id = ?', (event['id'],))
        event['images'] = [dict(img) for img in cursor.fetchall()]
        events.append(event)
    
    conn.close()
    return jsonify(events)


@app.route('/api/slider', methods=['GET'])
def get_slider_images():
    """Get all images with event details for the slider display."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all images joined with their event data
    cursor.execute('''
        SELECT 
            ei.id as image_id,
            ei.filename,
            e.id as event_id,
            e.title,
            e.description,
            e.event_date,
            e.event_time,
            e.location,
            e.category,
            e.author,
            e.author_initials
        FROM event_images ei
        JOIN events e ON ei.event_id = e.id
        ORDER BY e.event_date ASC, ei.uploaded_at DESC
    ''')
    
    slides = []
    for row in cursor.fetchall():
        slides.append({
            'image_id': row['image_id'],
            'image': f"/uploads/{row['filename']}",
            'event_id': row['event_id'],
            'title': row['title'],
            'description': row['description'],
            'date': row['event_date'],
            'time': row['event_time'],
            'location': row['location'],
            'category': row['category'],
            'author': row['author'],
            'author_initials': row['author_initials']
        })
    
    conn.close()
    return jsonify(slides)


@app.route('/api/events/stats', methods=['GET'])
def get_stats():
    """Get event statistics for admin dashboard."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM events')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM events WHERE event_date >= date("now")')
    upcoming = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM event_images')
    total_images = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'upcoming': upcoming,
        'total_images': total_images
    })


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """Get a single event by ID with its images."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()
    
    if row:
        event = dict(row)
        cursor.execute('SELECT * FROM event_images WHERE event_id = ?', (event_id,))
        event['images'] = [dict(img) for img in cursor.fetchall()]
        conn.close()
        return jsonify(event)
    
    conn.close()
    return jsonify({'error': 'Event not found'}), 404


@app.route('/api/events', methods=['POST'])
@api_login_required
def create_event():
    """Create a new event."""
    data = request.form.to_dict()
    
    # All fields are optional
    title = data.get('title', '')
    description = data.get('description', '')
    event_date = data.get('event_date', '')
    event_time = data.get('event_time', '')
    location = data.get('location', '')
    author = data.get('author', '')
    author_initials = data.get('author_initials', '')
    
    category = data.get('category', 'general')
    if category not in ['general', 'academic', 'social', 'spiritual', 'career']:
        category = 'general'
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO events (title, description, event_date, event_time, location, category, author, author_initials)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, event_date, event_time, location, category, author, author_initials))
    
    event_id = cursor.lastrowid
    
    # Handle file uploads
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                # Save to database
                cursor.execute('''
                    INSERT INTO event_images (event_id, filename, original_name)
                    VALUES (?, ?, ?)
                ''', (event_id, unique_filename, secure_filename(file.filename)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'id': event_id, 'message': 'Event created successfully'}), 201


@app.route('/api/events/<int:event_id>', methods=['PUT'])
@api_login_required
def update_event(event_id):
    """Update an existing event."""
    data = request.form.to_dict() if request.form else request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    
    update_fields = []
    values = []
    
    for field in ['title', 'description', 'event_date', 'event_time', 'location', 'category', 'author', 'author_initials']:
        if field in data:
            update_fields.append(f'{field} = ?')
            values.append(data[field])
    
    if update_fields:
        values.append(event_id)
        query = f'UPDATE events SET {", ".join(update_fields)} WHERE id = ?'
        cursor.execute(query, values)
    
    # Handle new file uploads
    if request.files and 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                cursor.execute('''
                    INSERT INTO event_images (event_id, filename, original_name)
                    VALUES (?, ?, ?)
                ''', (event_id, unique_filename, secure_filename(file.filename)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Event updated successfully'})


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@api_login_required
def delete_event(event_id):
    """Delete an event and its images."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    
    # Get and delete image files
    cursor.execute('SELECT filename FROM event_images WHERE event_id = ?', (event_id,))
    for row in cursor.fetchall():
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    # Delete from database (cascade will handle event_images)
    cursor.execute('DELETE FROM event_images WHERE event_id = ?', (event_id,))
    cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Event deleted successfully'})


@app.route('/api/events/<int:event_id>/images/<int:image_id>', methods=['DELETE'])
@api_login_required
def delete_image(event_id, image_id):
    """Delete a single image from an event."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT filename FROM event_images WHERE id = ? AND event_id = ?', (image_id, event_id))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Image not found'}), 404
    
    # Delete file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete from database
    cursor.execute('DELETE FROM event_images WHERE id = ?', (image_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Image deleted successfully'})


@app.route('/api/events/category/<category>', methods=['GET'])
def get_events_by_category(category):
    """Get events filtered by category."""
    if category not in ['general', 'academic', 'social', 'spiritual', 'career']:
        return jsonify({'error': 'Invalid category'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM events 
        WHERE category = ?
        ORDER BY event_date ASC
    ''', (category,))
    
    events = []
    for row in cursor.fetchall():
        event = dict(row)
        cursor.execute('SELECT * FROM event_images WHERE event_id = ?', (event['id'],))
        event['images'] = [dict(img) for img in cursor.fetchall()]
        events.append(event)
    
    conn.close()
    return jsonify(events)


if __name__ == '__main__':
    init_db()
    print("=" * 55)
    print("  Calendar of Events - Image Slider Server")
    print("  BYU-Pathway Worldwide")
    print("=" * 55)
    print("\nServer running at http://0.0.0.0:5000")
    print("\nPages:")
    print("  /       - Infinite autoplay image slider display")
    print("  /login  - Admin login page")
    print("  /admin  - Admin dashboard (requires login)")
    print(f"\nDefault admin credentials: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print("(Set ADMIN_USERNAME and ADMIN_PASSWORD env vars in production)")
    print("\nAPI Endpoints:")
    print("  GET    /api/events                     - Get all events")
    print("  GET    /api/slider                     - Get slider images")
    print("  GET    /api/events/stats               - Get event counts")
    print("  GET    /api/events/<id>                - Get single event")
    print("  POST   /api/events                     - Create event")
    print("  PUT    /api/events/<id>                - Update event")
    print("  DELETE /api/events/<id>                - Delete event")
    print("  DELETE /api/events/<id>/images/<img>   - Delete image")
    print("  GET    /api/events/category/<cat>      - Filter by category")
    print("\nPress Ctrl+C to stop the server\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
