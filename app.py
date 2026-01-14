from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DATABASE = 'message_board.db'

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with the messages table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('announcement', 'notice')),
            priority TEXT DEFAULT 'normal' CHECK(priority IN ('normal', 'urgent', 'pinned')),
            author TEXT NOT NULL,
            author_initials TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data if table is empty
    cursor.execute('SELECT COUNT(*) FROM messages')
    if cursor.fetchone()[0] == 0:
        sample_messages = [
            ('System Maintenance Scheduled for This Weekend', 
             'Our servers will undergo scheduled maintenance on Saturday from 2:00 AM to 6:00 AM EST. Please save your work and expect brief service interruptions.',
             'announcement', 'urgent', 'IT Department', 'IT'),
            ('Welcome to Our New Community Platform!',
             'We\'re excited to launch our redesigned message board. Explore new features including real-time updates, better organization, and improved accessibility.',
             'announcement', 'pinned', 'Admin Team', 'AD'),
            ('Q1 Town Hall Meeting - Save the Date',
             'Join us on January 25th at 3:00 PM for our quarterly town hall. Topics include company updates, team achievements, and Q&A with leadership.',
             'announcement', 'normal', 'Human Resources', 'HR'),
            ('Parking Lot B Closed for Repairs',
             'Parking Lot B will be closed January 15-17 for resurfacing. Please use Lots A or C during this time. We apologize for any inconvenience.',
             'notice', 'normal', 'Facilities', 'FM'),
            ('Updated Office Hours Starting February',
             'Beginning February 1st, office hours will change to 8:00 AM - 5:00 PM Monday through Thursday, and 8:00 AM - 3:00 PM on Fridays.',
             'notice', 'pinned', 'Operations', 'OP'),
            ('Cafeteria Menu Update',
             'New vegetarian and vegan options are now available at the cafeteria! Check out the expanded salad bar and daily plant-based specials.',
             'notice', 'normal', 'Cafeteria', 'CF'),
            ('Lost & Found: Items Available for Pickup',
             'Several items including a blue umbrella, wireless earbuds, and a black notebook have been turned in. Visit the reception desk to claim.',
             'notice', 'normal', 'Reception', 'RC'),
        ]
        cursor.executemany('''
            INSERT INTO messages (title, content, type, priority, author, author_initials)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_messages)
    
    conn.commit()
    conn.close()

# ==================== PAGE ROUTES ====================

@app.route('/')
def display_page():
    """Public display page showing all messages."""
    return render_template('display.html')

@app.route('/admin')
def admin_page():
    """Admin dashboard for managing messages."""
    return render_template('admin.html')

# ==================== API ROUTES ====================

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get all messages, ordered by priority and date."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages 
        ORDER BY 
            CASE priority 
                WHEN 'urgent' THEN 1 
                WHEN 'pinned' THEN 2 
                ELSE 3 
            END,
            created_at DESC
    ''')
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(messages)

@app.route('/api/messages/<int:message_id>', methods=['GET'])
def get_message(message_id):
    """Get a single message by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({'error': 'Message not found'}), 404

@app.route('/api/messages', methods=['POST'])
def create_message():
    """Create a new message."""
    data = request.get_json()
    
    required_fields = ['title', 'content', 'type', 'author', 'author_initials']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    if data['type'] not in ['announcement', 'notice']:
        return jsonify({'error': 'Type must be "announcement" or "notice"'}), 400
    
    priority = data.get('priority', 'normal')
    if priority not in ['normal', 'urgent', 'pinned']:
        priority = 'normal'
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (title, content, type, priority, author, author_initials)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['title'], data['content'], data['type'], priority, data['author'], data['author_initials']))
    
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': message_id, 'message': 'Message created successfully'}), 201

@app.route('/api/messages/<int:message_id>', methods=['PUT'])
def update_message(message_id):
    """Update an existing message."""
    data = request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if message exists
    cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Message not found'}), 404
    
    # Build update query dynamically
    update_fields = []
    values = []
    
    for field in ['title', 'content', 'type', 'priority', 'author', 'author_initials']:
        if field in data:
            update_fields.append(f'{field} = ?')
            values.append(data[field])
    
    if not update_fields:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(message_id)
    query = f'UPDATE messages SET {", ".join(update_fields)} WHERE id = ?'
    cursor.execute(query, values)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Message updated successfully'})

@app.route('/api/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    """Delete a message."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Message not found'}), 404
    
    cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Message deleted successfully'})

@app.route('/api/messages/type/<message_type>', methods=['GET'])
def get_messages_by_type(message_type):
    """Get messages filtered by type (announcement or notice)."""
    if message_type not in ['announcement', 'notice']:
        return jsonify({'error': 'Type must be "announcement" or "notice"'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages 
        WHERE type = ?
        ORDER BY 
            CASE priority 
                WHEN 'urgent' THEN 1 
                WHEN 'pinned' THEN 2 
                ELSE 3 
            END,
            created_at DESC
    ''', (message_type,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(messages)

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  Message Board Server")
    print("  BYU-Pathway Worldwide")
    print("=" * 50)
    print("\nServer running at http://localhost:5000")
    print("\nPages:")
    print("  /       - Public display page")
    print("  /admin  - Admin dashboard")
    print("\nAPI Endpoints:")
    print("  GET    /api/messages             - Get all messages")
    print("  GET    /api/messages/<id>        - Get single message")
    print("  POST   /api/messages             - Create message")
    print("  PUT    /api/messages/<id>        - Update message")
    print("  DELETE /api/messages/<id>        - Delete message")
    print("  GET    /api/messages/type/<type> - Filter by type")
    print("\nPress Ctrl+C to stop the server\n")
    app.run(debug=True, port=5000)
