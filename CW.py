import mysql.connector
from mysql.connector import Error
import csv
import plotly.graph_objects as go
import plotly.io as pio  # <--- ADDED: To match teacher's script
import functools

# --- CONFIGURE PLOTLY TO MATCH TEACHER'S SCRIPT ---
pio.renderers.default = "browser"

# --- DATABASE CONNECTION ---
def create_mysql_connection():
    """Creates and returns a MySQL connection."""
    host_name = "localhost"
    user_name = "root"      
    user_password = "password"  # <--- !!! UPDATE THIS !!!
    db_name = "football_db"

    try:
        connection = mysql.connector.connect(
            host=host_name,
            user=user_name,
            password=user_password
        )
        if connection.is_connected():
            print(f"Successfully connected to MySQL")
            return connection, db_name
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None, None

# --- RESET & SETUP ---
def reset_database(connection, db_name):
    """Drops existing tables to prevent errors on re-runs."""
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    cursor.execute(f"USE {db_name}")
    
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    tables = [
        'PLAYS', 'GOALKEEPER', 'OUTFIELD', 
        'FAN', 'PLAYER', 'COACH', 
        'MATCH_TABLE', 'CLUB'
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Dropped table '{table}' (if it existed).")
    
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    cursor.close()

def create_tables(connection):
    """Creates the 8 tables and the 2 Triggers."""
    try:
        cursor = connection.cursor()

        # 1. CLUB
        cursor.execute("""
        CREATE TABLE CLUB (
            club_id INT NOT NULL,
            club_name VARCHAR(100),
            city VARCHAR(100),
            stadium_name VARCHAR(100),
            PRIMARY KEY (club_id)
        )""")
       
        # 2. MATCH_TABLE
        cursor.execute("""
        CREATE TABLE MATCH_TABLE (
            match_id INT NOT NULL,
            match_date DATE,
            stadium VARCHAR(100),
            PRIMARY KEY (match_id)
        )""")

        # 3. COACH
        cursor.execute("""
        CREATE TABLE COACH (
            coach_id INT NOT NULL,
            coach_name VARCHAR(100),
            nationality VARCHAR(100),
            club_id INT NOT NULL,
            PRIMARY KEY (coach_id),
            FOREIGN KEY (club_id) REFERENCES CLUB(club_id) ON DELETE CASCADE,
            UNIQUE (club_id)
        )""")

        # 4. PLAYER
        cursor.execute("""
        CREATE TABLE PLAYER (
            player_id INT NOT NULL,
            player_name VARCHAR(100),
            club_id INT NOT NULL,
            age INT,
            nationality VARCHAR(100),
            position VARCHAR(10),
            PRIMARY KEY (player_id),
            FOREIGN KEY (club_id) REFERENCES CLUB(club_id) ON DELETE CASCADE
        )""")

        # 5. GOALKEEPER
        cursor.execute("""
        CREATE TABLE GOALKEEPER (
            player_id INT NOT NULL,
            saves INT,
            clean_sheets INT,
            PRIMARY KEY (player_id),
            FOREIGN KEY (player_id) REFERENCES PLAYER(player_id) ON DELETE CASCADE
        )""")

        # 6. OUTFIELD
        cursor.execute("""
        CREATE TABLE OUTFIELD (
            player_id INT NOT NULL,
            goals INT,
            assists INT,
            PRIMARY KEY (player_id),
            FOREIGN KEY (player_id) REFERENCES PLAYER(player_id) ON DELETE CASCADE
        )""")

        # 7. FAN
        cursor.execute("""
        CREATE TABLE FAN (
            fan_id INT NOT NULL,
            fan_name VARCHAR(100),
            city VARCHAR(100),
            club_id INT NOT NULL,
            PRIMARY KEY (fan_id),
            FOREIGN KEY (club_id) REFERENCES CLUB(club_id) ON DELETE CASCADE
        )""")

        # 8. PLAYS
        cursor.execute("""
        CREATE TABLE PLAYS (
            match_id INT NOT NULL,
            club_id INT NOT NULL,
            side VARCHAR(10),
            goals_scored INT,
            points INT,
            PRIMARY KEY (match_id, club_id),
            FOREIGN KEY (match_id) REFERENCES MATCH_TABLE(match_id) ON DELETE CASCADE,
            FOREIGN KEY (club_id) REFERENCES CLUB(club_id) ON DELETE CASCADE
        )""")

        # --- TRIGGER 1: AUTO-ALLOCATION (The Robot) ---
        # Automatiacally creates an empty row in GK or Outfield when a Player is added.
        print("Creating Auto-Allocation Trigger...")
        trigger_sql = """
        CREATE TRIGGER auto_allocate_position
        AFTER INSERT ON PLAYER
        FOR EACH ROW
        BEGIN
            IF NEW.position = 'GK' THEN
                INSERT INTO GOALKEEPER (player_id, saves, clean_sheets) 
                VALUES (NEW.player_id, 0, 0);
            ELSE
                INSERT INTO OUTFIELD (player_id, goals, assists) 
                VALUES (NEW.player_id, 0, 0);
            END IF;
        END
        """
        cursor.execute(trigger_sql)

        # --- TRIGGER 2: SECURITY GUARD (Prevent Updates) ---
        # Stops you from creating "Zombie Data" by changing positions later.
        print("Creating Security Trigger (Prevent Position Updates)...")
        security_trigger = """
        CREATE TRIGGER prevent_position_change
        BEFORE UPDATE ON PLAYER
        FOR EACH ROW
        BEGIN
            IF NEW.position <> OLD.position THEN
                SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Error: Player Position is permanent and cannot be changed.';
            END IF;
        END
        """
        cursor.execute(security_trigger) 

        print("All 8 Tables and 2 Triggers created successfully.")
        cursor.close()
    except Error as e:
        print(f"Error creating tables: {e}")

# --- POPULATE TABLES ---
def load_csv_insert(cursor, filename, table_name, columns_count):
    """Standard Insert for regular tables."""
    try:
        print(f"Loading {table_name} from {filename}...")
        with open(filename, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            next(csv_reader) # Skip Header
            data = list(csv_reader)
            
            if data:
                placeholders = ", ".join(["%s"] * columns_count)
                query = f"INSERT INTO {table_name} VALUES ({placeholders})"
                cursor.executemany(query, data)
                print(f"   -> Inserted {len(data)} rows.")
    except Exception as e:
        print(f"   -> Error loading {table_name}: {e}")

def load_csv_update_goalkeeper(cursor, filename):
    """Special Update for Goalkeepers (Rows exist due to Trigger)."""
    try:
        print(f"Updating GOALKEEPER stats from {filename}...")
        with open(filename, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            # CSV: [player_id, saves, clean_sheets]
            # Query needs: (saves, clean_sheets, player_id)
            data = []
            for row in csv_reader:
                data.append((row[1], row[2], row[0])) 
            
            if data:
                query = "UPDATE GOALKEEPER SET saves=%s, clean_sheets=%s WHERE player_id=%s"
                cursor.executemany(query, data)
                print(f"   -> Updated {len(data)} Goalkeepers.")
    except Exception as e:
        print(f"   -> Error updating Goalkeepers: {e}")

def load_csv_update_outfield(cursor, filename):
    """Special Update for Outfield (Rows exist due to Trigger)."""
    try:
        print(f"Updating OUTFIELD stats from {filename}...")
        with open(filename, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            # CSV: [player_id, goals, assists]
            # Query needs: (goals, assists, player_id)
            data = []
            for row in csv_reader:
                data.append((row[1], row[2], row[0])) 
            
            if data:
                query = "UPDATE OUTFIELD SET goals=%s, assists=%s WHERE player_id=%s"
                cursor.executemany(query, data)
                print(f"   -> Updated {len(data)} Outfield players.")
    except Exception as e:
        print(f"   -> Error updating Outfield players: {e}")

def populate_tables(connection):
    cursor = connection.cursor()
    
    # 1. Standard Tables
    load_csv_insert(cursor, 'club.csv', 'CLUB', 4)
    load_csv_insert(cursor, 'match.csv', 'MATCH_TABLE', 3)
    load_csv_insert(cursor, 'coach.csv', 'COACH', 4)
    
    # 2. Main Player Table (Trigger fires here!)
    load_csv_insert(cursor, 'player.csv', 'PLAYER', 6)
    
    # 3. Subtype Tables (Using Update logic now)
    load_csv_update_goalkeeper(cursor, 'goalkeeper.csv')
    load_csv_update_outfield(cursor, 'outfield.csv')
    
    # 4. Remaining Standard Tables
    load_csv_insert(cursor, 'fan.csv', 'FAN', 4)
    load_csv_insert(cursor, 'plays.csv', 'PLAYS', 5)

    connection.commit()
    cursor.close()

# --- VISUALIZATION & QUERIES ---
def run_queries_and_plot(connection):
    cursor = connection.cursor()

    # --- QUERY 1: LEAGUE TABLE ---
    print("\n--- Generating Query 1 (La Liga Table 2024/25) ---")
    
    reconstruct_match_query = """
        SELECT 
            c1.club_name AS HomeTeam, 
            c2.club_name AS AwayTeam, 
            p1.goals_scored AS FTHG, 
            p2.goals_scored AS FTAG
        FROM PLAYS p1
        JOIN PLAYS p2 ON p1.match_id = p2.match_id AND p1.club_id != p2.club_id
        JOIN CLUB c1 ON p1.club_id = c1.club_id
        JOIN CLUB c2 ON p2.club_id = c2.club_id
        WHERE p1.side = 'Home'
    """

    cursor.execute(reconstruct_match_query)
    all_matches = cursor.fetchall()

    team_stats = {}
    head_to_head = {}

    cursor.execute("SELECT club_name FROM CLUB")
    clubs_list = cursor.fetchall()
    for row in clubs_list:
        club = row[0]
        team_stats[club] = {'points': 0, 'goals_for': 0, 'goals_against': 0}

    for row in all_matches:
        h_team = row[0]
        a_team = row[1]
        h_score = row[2]
        a_score = row[3]

        team_stats[h_team]['goals_for'] += h_score
        team_stats[h_team]['goals_against'] += a_score
        team_stats[a_team]['goals_for'] += a_score
        team_stats[a_team]['goals_against'] += h_score

        if h_score > a_score:
            team_stats[h_team]['points'] += 3
            h_points = 3; a_points = 0
        elif a_score > h_score:
            team_stats[a_team]['points'] += 3
            h_points = 0; a_points = 3
        else:
            team_stats[h_team]['points'] += 1
            team_stats[a_team]['points'] += 1
            h_points = 1; a_points = 1

        matchup_key = tuple(sorted((h_team, a_team)))
        if matchup_key not in head_to_head:
            head_to_head[matchup_key] = {
                h_team: {'pts': 0, 'goal_diff': 0},
                a_team: {'pts': 0, 'goal_diff': 0}
            }
        
        head_to_head[matchup_key][h_team]['pts'] += h_points
        head_to_head[matchup_key][h_team]['goal_diff'] += (h_score - a_score)
        head_to_head[matchup_key][a_team]['pts'] += a_points
        head_to_head[matchup_key][a_team]['goal_diff'] += (a_score - h_score)

    def compare_teams(t1, t2):
        stats1 = team_stats[t1]
        stats2 = team_stats[t2]

        if stats1['points'] > stats2['points']: return -1
        elif stats2['points'] > stats1['points']: return 1
        
        matchup_key = tuple(sorted((t1, t2)))
        if matchup_key in head_to_head:
            record = head_to_head[matchup_key]
            if record[t1]['pts'] > record[t2]['pts']: return -1
            elif record[t2]['pts'] > record[t1]['pts']: return 1
            if record[t1]['goal_diff'] > record[t2]['goal_diff']: return -1
            elif record[t2]['goal_diff'] > record[t1]['goal_diff']: return 1

        gd1 = stats1['goals_for'] - stats1['goals_against']
        gd2 = stats2['goals_for'] - stats2['goals_against']
        if gd1 > gd2: return -1
        elif gd2 > gd1: return 1

        if stats1['goals_for'] > stats2['goals_for']: return -1
        elif stats2['goals_for'] > stats1['goals_for']: return 1
        return 0

    sorted_teams = sorted(team_stats.keys(), key=functools.cmp_to_key(compare_teams))

    if sorted_teams:
        list_teams = []
        list_points = []
        for team in sorted_teams:
            list_teams.append(team)
            list_points.append(team_stats[team]['points'])

        fig = go.Figure(data=[
            go.Bar(
                x=list_teams, 
                y=list_points,
                text=list_points,
                textposition='auto',
                marker=dict(color=list_points, colorscale='Viridis', showscale=True)
            )
        ])
        fig.update_layout(
            title='La Liga Table 2024/25 (Official Standings)',
            xaxis_title='Team',
            yaxis_title='Points'
        )
        
        fig.show()

    # --- QUERY 2: TOP GOALSCORERS ---
    print("\n--- Generating Query 2 (Top Goalscorers) ---")
    query1 = """
        SELECT p.player_name, SUM(o.goals) as TotalGoals 
        FROM PLAYER p 
        JOIN OUTFIELD o ON p.player_id = o.player_id 
        GROUP BY p.player_name
        ORDER BY TotalGoals DESC 
        LIMIT 10
    """
    cursor.execute(query1)
    data_q2 = cursor.fetchall()
    
    if data_q2:
        data_q2_sorted = sorted(data_q2, key=lambda x: x[1])
        names = [row[0] for row in data_q2_sorted]
        goals = [row[1] for row in data_q2_sorted]

        fig = go.Figure(data=[
            go.Bar(
                x=goals, 
                y=names, 
                orientation='h',
                text=goals,
                textposition='auto',
                marker=dict(color=goals, colorscale='Plasma', showscale=True)
            )
        ])
        fig.update_layout(
            title='Top 10 Goalscorers 2024/25',
            xaxis_title='Goals',
            yaxis_title='Player Name'
        )
     
        fig.show()

    # --- QUERY 3: TOP GOALKEEPERS ---
    print("\n--- Generating Query 3 (Top 5 Goalkeepers) ---")
    query4 = """
        SELECT p.player_name, c.club_name, g.saves 
        FROM PLAYER p 
        JOIN GOALKEEPER g ON p.player_id = g.player_id 
        JOIN CLUB c ON p.club_id = c.club_id
        ORDER BY g.saves DESC 
        LIMIT 5
    """
    cursor.execute(query4)
    data_q3 = cursor.fetchall()
    
    if data_q3:
        names = [row[0] for row in data_q3]
        clubs = [row[1] for row in data_q3]
        saves = [row[2] for row in data_q3]
        labels = [f"{n} ({c})" for n, c in zip(names, clubs)]

        fig = go.Figure(data=[
            go.Bar(
                x=labels, 
                y=saves,
                text=saves,
                textposition='auto',
                marker=dict(color=saves, colorscale='Bluered')
            )
        ])
        fig.update_layout(
            title='Top 5 Goalkeepers (Most Saves)',
            xaxis_title='Goalkeeper (Club)',
            yaxis_title='Total Saves'
        )
   
        fig.show()

    # --- QUERY 4: PLAYER NATIONALITIES ---
    print("\n--- Generating Query 4 (Player Nationalities) ---")
    cursor.execute("""
        SELECT CASE WHEN nationality = 'Spain' THEN 'Spanish' ELSE 'Foreign' END AS Cat, 
        COUNT(*) FROM PLAYER GROUP BY Cat
    """)
    data_q4 = cursor.fetchall()
    
    if data_q4:
        categories = [row[0] for row in data_q4]
        counts = [row[1] for row in data_q4]

        fig = go.Figure(data=[
            go.Pie(labels=categories, values=counts, hole=.3)
        ])
        fig.update_layout(title='Player Demographics 2024/25: Spanish vs Foreign')
      
        fig.show()

    # --- QUERY 5: COACH NATIONALITIES ---
    print("\n--- Generating Query 5 (Coach Nationalities) ---")
    query6 = """
        SELECT nationality, COUNT(*) as Count 
        FROM COACH 
        GROUP BY nationality 
        ORDER BY Count DESC 
    """
    cursor.execute(query6)
    data_q5 = cursor.fetchall()
    
    if data_q5:
        nationalities = [row[0] for row in data_q5]
        counts = [row[1] for row in data_q5]

        fig = go.Figure(data=[
            go.Pie(labels=nationalities, values=counts)
        ])
        fig.update_layout(title='Club Coaches Nationalities')
  
        fig.show()

    # --- QUERY 6: FAN SUPPORT ---
    print("\n--- Generating Query 6 (Clubs by Fan Support) ---")
    query5 = """
        SELECT c.club_name, COUNT(f.fan_id) as FanCount 
        FROM CLUB c 
        JOIN FAN f ON c.club_id = f.club_id 
        GROUP BY c.club_name 
        ORDER BY FanCount DESC
    """
    cursor.execute(query5)
    data_q6 = cursor.fetchall()
    
    if data_q6:
        clubs = [row[0] for row in data_q6]
        fans = [row[1] for row in data_q6]

        fig = go.Figure(data=[
            go.Bar(
                x=clubs, 
                y=fans,
                text=fans,
                textposition='auto',
                marker=dict(color=fans, colorscale='Magma')
            )
        ])
        fig.update_layout(
            title='Clubs with the Most Fans',
            xaxis_title='Club',
            yaxis_title='Fan Count'
        )
       
        fig.show()

    cursor.close()

# --- MAIN ---
if __name__ == "__main__":
    conn, db_name = create_mysql_connection()
    
    if conn:
        reset_database(conn, db_name) 
        create_tables(conn)
        populate_tables(conn)
        run_queries_and_plot(conn)
        conn.close()
        print("\nComplete. Check your browser for the opened tabs.")