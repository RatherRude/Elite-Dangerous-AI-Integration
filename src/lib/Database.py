import json
import os
import time
import random
import sqlean
import sqlite3
from typing import Any, final, List, Dict, Optional, Tuple, Type, TypeVar, Generic, cast
import sqlite_vec
from .Logger import log

from .Config import get_cn_appdata_path

def get_db_path() -> str:
    db_path = os.path.join(get_cn_appdata_path(), 'covas.db')
    return db_path

def _execute_with_retry(cursor, query, params=(), max_retries=5, initial_backoff=0.1):
    """Execute a SQL query with retry logic for database locks"""
    for attempt in range(max_retries):
        try:
            cursor.execute(query, params)
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                # Calculate backoff with exponential increase and jitter
                backoff = initial_backoff * (2 ** attempt) + (random.random() * initial_backoff)
                time.sleep(backoff)
            else:
                raise

# Global connection for SQLite
_db_connection = None

def get_connection():
    """Get the shared SQLite database connection"""
    global _db_connection
    if _db_connection is None:
        # Create and configure the connection
        _db_connection = sqlite3.connect(get_db_path())
        # Configure SQLite for better performance and fewer locking issues
        _db_connection.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging mode
        _db_connection.execute("PRAGMA synchronous = NORMAL")  # Less synchronous durability for better performance
        _db_connection.execute("PRAGMA busy_timeout = 5000")  # Wait up to 5 seconds on database locks
        _db_connection.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
        
        # Load vector extension
        _db_connection.enable_load_extension(True)
        sqlite_vec.load(_db_connection)
        _db_connection.enable_load_extension(False)
    
    return _db_connection

def close_connection():
    """Close the shared SQLite database connection"""
    global _db_connection
    if _db_connection is not None:
        try:
            _db_connection.close()
        except Exception as e:
            log('error', f"Error closing database connection: {e}")
        finally:
            _db_connection = None

def instantiate_class_by_name(self, classes: list[Any], class_name: str, data: dict[str, Any]) -> Any:
    for cls in classes:
        if cls.__name__ == class_name:
            return cls(**data)
    return None

@final
class EventStore():
    def __init__(self, store_name: str, event_classes: list[Any]):
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        self.event_classes = event_classes
        
        try:
            _execute_with_retry(self.cursor, f'''                
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class TEXT,
                    data TEXT,
                    processed_at FLOAT,
                    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            log('error', f"Error creating event store table {self.table_name}: {e}")
        
    def __del__(self):
        if hasattr(self, 'cursor'):
            try:
                self.cursor.close()
            except Exception:
                pass
    
    def commit(self) -> None:
        try:
            self.conn.commit()
        except Exception as e:
            log('error', f"Error committing to event store: {e}")
    
    def insert_event(self, event: Any, processed_at: float, commit: bool = True) -> None:
        try:
            event_data = json.dumps(event.__dict__)
            event_class = event.__class__.__name__
            _execute_with_retry(self.cursor, f'''
                INSERT INTO {self.table_name} (class, data, processed_at)
                VALUES (?, ?, ?)
            ''', (event_class, event_data, processed_at))
            
            if commit:
                self.conn.commit()
        except Exception as e:
            log('error', f"Error inserting event: {e}")
    
    def get_latest(self, limit: int = 100) -> list[Any]:
        try:
            _execute_with_retry(self.cursor, f'''
                SELECT class, data, processed_at
                FROM {self.table_name}
                ORDER BY processed_at DESC
                LIMIT (?)
            ''', (limit,))
            
            rows = self.cursor.fetchall()
            events = []
            for row in rows:
                instance = instantiate_class_by_name(self, self.event_classes, row[0], json.loads(row[1]))
                events.append(instance)
            return events
        except Exception as e:
            log('error', f"Error getting latest events: {e}")
            return []
    
    def delete_all(self) -> None:
        try:
            _execute_with_retry(self.cursor, f'''
                DELETE FROM {self.table_name}
            ''')
            self.conn.commit()
        except Exception as e:
            log('error', f"Error deleting all events: {e}")

@final
class KeyValueStore():
    def __init__(self, store_name: str):
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        
        try:
            _execute_with_retry(self.cursor, f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    version TEXT,
                    value TEXT,
                    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            log('error', f"Error creating key-value store table {self.table_name}: {e}")
                    
    def __del__(self):
        if hasattr(self, 'cursor'):
            try:
                self.cursor.close()
            except Exception:
                pass
                        
    def get_version(self, key: str) -> str | None:
        try:
            _execute_with_retry(self.cursor, f'''
                SELECT version
                FROM {self.table_name}
                WHERE key = ?
            ''', (key,))
            
            row = self.cursor.fetchone()
            if row:
                return row[0]
            return None
        except Exception as e:
            log('error', f"Error getting version for key {key}: {e}")
            return None
        
    def init(self, key: str, version: str, value: Any) -> Any:
        try:
            current_version = self.get_version(key)
            if current_version == version:
                return self.get(key)
            
            _execute_with_retry(self.cursor, f'''
                INSERT OR REPLACE INTO {self.table_name} (key, version, value)
                VALUES (?, ?, ?)
            ''', (key, version, json.dumps(value)))
            
            self.conn.commit()
            return self.get(key)
        except Exception as e:
            log('error', f"Error initializing key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        try:
            _execute_with_retry(self.cursor, f'''
                UPDATE {self.table_name}
                SET value = ?
                WHERE key = ?
            ''', (json.dumps(value), key))
            
            self.conn.commit()
        except Exception as e:
            log('error', f"Error setting value for key {key}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            _execute_with_retry(self.cursor, f'''
                SELECT value
                FROM {self.table_name}
                WHERE key = ?
            ''', (key,))
            
            row = self.cursor.fetchone()
            if row:
                return json.loads(row[0])
            return default
        except Exception as e:
            log('error', f"Error getting value for key {key}: {e}")
            return default

    def get_all(self) -> dict[str, Any]:
        try:
            _execute_with_retry(self.cursor, f'''
                SELECT key, value
                FROM {self.table_name}
            ''')
            
            rows = self.cursor.fetchall()
            result = {}
            for row in rows:
                try:
                    result[row[0]] = json.loads(row[1])
                except Exception:
                    pass
            return result
        except Exception as e:
            log('error', f"Error getting all key-value pairs: {e}")
            return {}
    
    def delete(self, key: str) -> None:
        try:
            _execute_with_retry(self.cursor, f'''
                DELETE FROM {self.table_name}
                WHERE key = ?
            ''', (key,))
            
            self.conn.commit()
        except Exception as e:
            log('error', f"Error deleting key {key}: {e}")
    
    def delete_all(self) -> None:
        try:
            _execute_with_retry(self.cursor, f'''
                DELETE FROM {self.table_name}
            ''')
            
            self.conn.commit()
        except Exception as e:
            log('error', f"Error deleting all key-value pairs: {e}")

T = TypeVar('T')

@final
class Table(Generic[T]):
    """Generic SQL table operations for storing and retrieving structured data."""
    
    def __init__(self, table_name: str, schema: Dict[str, str], primary_key: str = 'id'):
        """
        Initialize a new table with the given schema.
        
        Args:
            table_name: Name for the table (will be prefixed with v1)
            schema: Dictionary mapping column names to their SQL types
            primary_key: The primary key column name
        """
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        self.table_name = f'{table_name}_v1'
        self.schema = schema
        self.primary_key = primary_key
        
        # Create the table if it doesn't exist
        try:
            columns = [f"{name} {type_}" for name, type_ in schema.items()]
            schema_str = ", ".join(columns)
            
            _execute_with_retry(self.cursor, f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    {schema_str},
                    PRIMARY KEY ({primary_key})
                )
            ''')
            self.conn.commit()
        except Exception as e:
            log('error', f"Error creating table {self.table_name}: {e}")
    
    def __del__(self):
        if hasattr(self, 'cursor'):
            try:
                self.cursor.close()
            except Exception:
                pass
    
    def insert(self, data: Dict[str, Any], replace: bool = False) -> int | None:
        """
        Insert a new row into the table.
        
        Args:
            data: Dictionary mapping column names to values
            replace: If True, replace existing row with same primary key
            
        Returns:
            The rowid of the inserted row, or None if an error occurred
        """
        try:
            columns = []
            placeholders = []
            values = []
            
            for column, value in data.items():
                if column in self.schema:
                    columns.append(column)
                    placeholders.append('?')
                    
                    # Handle JSON serialization for complex types
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
            
            if not columns:
                log('warn', f"Warning: No valid columns found for insert into {self.table_name}")
                return None
                
            columns_str = ', '.join(columns)
            placeholders_str = ', '.join(placeholders)
            
            insert_type = "INSERT OR REPLACE" if replace else "INSERT"
            
            query = f'''
                {insert_type} INTO {self.table_name} ({columns_str})
                VALUES ({placeholders_str})
            '''
            
            _execute_with_retry(self.cursor, query, tuple(values))
            self.conn.commit()
            
            return self.cursor.lastrowid
        except Exception as e:
            log('error', f"Error inserting data into {self.table_name}: {e}")
            return None
    
    def update(self, primary_key_value: Any, data: Dict[str, Any]) -> None:
        """
        Update a row in the table.
        
        Args:
            primary_key_value: Value of the primary key for the row to update
            data: Dictionary mapping column names to new values
        """
        try:
            set_clauses = []
            values = []
            
            for column, value in data.items():
                if column in self.schema and column != self.primary_key:
                    set_clauses.append(f"{column} = ?")
                    
                    # Handle JSON serialization for complex types
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
            
            if not set_clauses:
                return
            
            set_clause_str = ', '.join(set_clauses)
            values.append(primary_key_value)
            
            query = f'''
                UPDATE {self.table_name}
                SET {set_clause_str}
                WHERE {self.primary_key} = ?
            '''
            
            _execute_with_retry(self.cursor, query, tuple(values))
            self.conn.commit()
        except Exception as e:
            log('error', f"Error updating data in {self.table_name}: {e}")
    
    def get(self, primary_key_value: Any) -> Optional[Dict[str, Any]]:
        """
        Get a row from the table by primary key.
        
        Args:
            primary_key_value: Value of the primary key for the row to retrieve
            
        Returns:
            Dictionary with the row data or None if not found
        """
        try:
            query = f'''
                SELECT * FROM {self.table_name}
                WHERE {self.primary_key} = ?
            '''
            
            _execute_with_retry(self.cursor, query, (primary_key_value,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            # Get column names from cursor description
            columns = [desc[0] for desc in self.cursor.description]
            result = {}
            
            for i, column in enumerate(columns):
                value = row[i]
                # Try to parse JSON for complex types
                if value and column in self.schema and self.schema[column].upper() == 'TEXT':
                    try:
                        result[column] = json.loads(value)
                        continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                result[column] = value
            
            return result
        except Exception as e:
            log('error', f"Error getting row from {self.table_name}: {e}")
            return None
    
    def get_all(self, where_clause: Optional[str] = None, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Get all rows from the table, optionally filtered by a WHERE clause.
        
        Args:
            where_clause: Optional WHERE clause (without the 'WHERE' keyword)
            params: Parameters for the WHERE clause
            
        Returns:
            List of dictionaries with the row data
        """
        try:
            query = f"SELECT * FROM {self.table_name}"
            
            if where_clause:
                query += f" WHERE {where_clause}"
            
            _execute_with_retry(self.cursor, query, params or ())
            
            # Get column names from cursor description
            columns = [desc[0] for desc in self.cursor.description]
            results = []
            
            for row in self.cursor.fetchall():
                result = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Try to parse JSON for complex types
                    if value and column in self.schema and self.schema[column].upper() == 'TEXT':
                        try:
                            result[column] = json.loads(value)
                            continue
                        except (json.JSONDecodeError, TypeError):
                            pass
                    result[column] = value
                results.append(result)
            
            return results
        except Exception as e:
            log('error', f"Error getting all rows from {self.table_name}: {e}")
            return []
    
    def delete(self, primary_key_value: Any) -> None:
        """
        Delete a row from the table.
        
        Args:
            primary_key_value: Value of the primary key for the row to delete
        """
        try:
            query = f'''
                DELETE FROM {self.table_name}
                WHERE {self.primary_key} = ?
            '''
            
            _execute_with_retry(self.cursor, query, (primary_key_value,))
            self.conn.commit()
        except Exception as e:
            log('error', f"Error deleting row from {self.table_name}: {e}")
    
    def delete_all(self) -> None:
        """Delete all rows from the table."""
        try:
            query = f'''
                DELETE FROM {self.table_name}
            '''
            
            _execute_with_retry(self.cursor, query)
            self.conn.commit()
        except Exception as e:
            log('error', f"Error deleting all rows from {self.table_name}: {e}")
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a custom SQL query on the table.
        
        Args:
            query: SQL query to execute (use ? placeholders for parameters)
            params: Parameters for the query
            
        Returns:
            List of dictionaries with the result data
        """
        try:
            _execute_with_retry(self.cursor, query, params or ())
            
            # Get column names from cursor description
            columns = [desc[0] for desc in self.cursor.description]
            results = []
            
            for row in self.cursor.fetchall():
                result = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Try to parse JSON for complex types
                    if value and isinstance(value, str):
                        try:
                            result[column] = json.loads(value)
                            continue
                        except (json.JSONDecodeError, TypeError):
                            pass
                    result[column] = value
                results.append(result)
            
            return results
        except Exception as e:
            log('error', f"Error executing query on {self.table_name}: {e}")
            return []