"""
Database management module for speech-to-text application.
Handles SQLite operations for storing and retrieving transcriptions.
"""

import sqlite3
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TranscriptionDatabase:
    """Manages SQLite database for storing speech transcriptions."""
    
    def __init__(self, db_path: str = "transcriptions.db"):
        """
        Initialize database connection and create tables if they don't exist.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    duration REAL,
                    audio_file_path TEXT,
                    confidence REAL,
                    tags TEXT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster text searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transcriptions_text 
                ON transcriptions(text)
            """)
            
            # Create index for timestamp searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transcriptions_timestamp 
                ON transcriptions(timestamp)
            """)
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def add_transcription(
        self,
        text: str,
        duration: Optional[float] = None,
        audio_file_path: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Add a new transcription to the database.
        
        Args:
            text: Transcribed text
            duration: Duration of audio in seconds
            audio_file_path: Path to the audio file
            confidence: Confidence score from speech recognition
            tags: List of tags for categorization
            notes: Additional notes
            
        Returns:
            ID of the inserted transcription
        """
        tags_str = json.dumps(tags) if tags else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transcriptions 
                (text, duration, audio_file_path, confidence, tags, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (text, duration, audio_file_path, confidence, tags_str, notes))
            
            transcription_id = cursor.lastrowid
            conn.commit()
            
        logger.info(f"Added transcription with ID: {transcription_id}")
        return transcription_id
    
    def get_transcription(self, transcription_id: int) -> Optional[Dict]:
        """
        Get a specific transcription by ID.
        
        Args:
            transcription_id: ID of the transcription
            
        Returns:
            Dictionary containing transcription data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transcriptions WHERE id = ?
            """, (transcription_id,))
            
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Parse tags from JSON
                if result['tags']:
                    result['tags'] = json.loads(result['tags'])
                return result
        
        return None
    
    def search_transcriptions(
        self,
        query: str = "",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Search transcriptions with various filters.
        
        Args:
            query: Text to search for (case-insensitive)
            start_date: Start date for filtering
            end_date: End date for filtering
            tags: Tags to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of transcription dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            sql = "SELECT * FROM transcriptions WHERE 1=1"
            params = []
            
            # Add text search
            if query:
                sql += " AND text LIKE ?"
                params.append(f"%{query}%")
            
            # Add date filters
            if start_date:
                sql += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                sql += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            # Add tag filter
            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')
            
            # Add ordering and pagination
            sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = dict(row)
                # Parse tags from JSON
                if result['tags']:
                    result['tags'] = json.loads(result['tags'])
                results.append(result)
            
            return results
    
    def update_transcription(
        self,
        transcription_id: int,
        text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update an existing transcription.
        
        Args:
            transcription_id: ID of the transcription to update
            text: New text (optional)
            tags: New tags (optional)
            notes: New notes (optional)
            
        Returns:
            True if update was successful, False otherwise
        """
        updates = []
        params = []
        
        if text is not None:
            updates.append("text = ?")
            params.append(text)
        
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            sql = f"UPDATE transcriptions SET {', '.join(updates)} WHERE id = ?"
            params.append(transcription_id)
            
            cursor.execute(sql, params)
            success = cursor.rowcount > 0
            conn.commit()
            
        if success:
            logger.info(f"Updated transcription ID: {transcription_id}")
        
        return success
    
    def delete_transcription(self, transcription_id: int) -> bool:
        """
        Delete a transcription by ID.
        
        Args:
            transcription_id: ID of the transcription to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))
            success = cursor.rowcount > 0
            conn.commit()
        
        if success:
            logger.info(f"Deleted transcription ID: {transcription_id}")
        
        return success
    
    def get_statistics(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary containing various statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total transcriptions
            cursor.execute("SELECT COUNT(*) FROM transcriptions")
            total_count = cursor.fetchone()[0]
            
            # Total duration
            cursor.execute("SELECT SUM(duration) FROM transcriptions WHERE duration IS NOT NULL")
            total_duration = cursor.fetchone()[0] or 0
            
            # Average duration
            cursor.execute("SELECT AVG(duration) FROM transcriptions WHERE duration IS NOT NULL")
            avg_duration = cursor.fetchone()[0] or 0
            
            # Recent activity (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) FROM transcriptions 
                WHERE timestamp >= datetime('now', '-7 days')
            """)
            recent_count = cursor.fetchone()[0]
            
            # Most common tags
            cursor.execute("SELECT tags FROM transcriptions WHERE tags IS NOT NULL")
            all_tags = []
            for row in cursor.fetchall():
                if row[0]:
                    tags = json.loads(row[0])
                    all_tags.extend(tags)
            
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            return {
                'total_transcriptions': total_count,
                'total_duration_seconds': total_duration,
                'average_duration_seconds': avg_duration,
                'recent_transcriptions': recent_count,
                'most_common_tags': sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            }
    
    def export_to_csv(self, output_path: str, include_audio_paths: bool = False) -> bool:
        """
        Export all transcriptions to CSV file.
        
        Args:
            output_path: Path for the CSV file
            include_audio_paths: Whether to include audio file paths
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transcriptions ORDER BY timestamp")
                rows = cursor.fetchall()
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                if not rows:
                    return True
                
                fieldnames = ['id', 'text', 'timestamp', 'duration', 'confidence', 'tags', 'notes']
                if include_audio_paths:
                    fieldnames.append('audio_file_path')
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in rows:
                    row_dict = dict(row)
                    # Parse tags for better readability
                    if row_dict['tags']:
                        row_dict['tags'] = ', '.join(json.loads(row_dict['tags']))
                    
                    if not include_audio_paths:
                        row_dict.pop('audio_file_path', None)
                    
                    # Remove created_at and updated_at for cleaner export
                    row_dict.pop('created_at', None)
                    row_dict.pop('updated_at', None)
                    
                    writer.writerow(row_dict)
            
            logger.info(f"Exported {len(rows)} transcriptions to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False
    
    def export_to_json(self, output_path: str) -> bool:
        """
        Export all transcriptions to JSON file.
        
        Args:
            output_path: Path for the JSON file
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            transcriptions = self.search_transcriptions(limit=10000)  # Get all
            
            # Convert datetime objects to strings for JSON serialization
            for trans in transcriptions:
                if trans.get('timestamp'):
                    trans['timestamp'] = str(trans['timestamp'])
                if trans.get('created_at'):
                    trans['created_at'] = str(trans['created_at'])
                if trans.get('updated_at'):
                    trans['updated_at'] = str(trans['updated_at'])
            
            with open(output_path, 'w', encoding='utf-8') as jsonfile:
                json.dump({
                    'transcriptions': transcriptions,
                    'exported_at': datetime.now().isoformat(),
                    'total_count': len(transcriptions)
                }, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(transcriptions)} transcriptions to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for the backup file
            
        Returns:
            True if backup was successful, False otherwise
        """
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False


# Convenience functions
def create_database(db_path: str = "transcriptions.db") -> TranscriptionDatabase:
    """Create and return a new database instance."""
    return TranscriptionDatabase(db_path)


if __name__ == "__main__":
    # Test the database functionality
    db = TranscriptionDatabase("test_transcriptions.db")
    
    # Add some test data
    trans_id = db.add_transcription(
        text="Hello, this is a test transcription.",
        duration=3.5,
        confidence=0.95,
        tags=["test", "demo"],
        notes="This is a test note"
    )
    
    print(f"Added transcription with ID: {trans_id}")
    
    # Search transcriptions
    results = db.search_transcriptions(query="test")
    print(f"Found {len(results)} transcriptions with 'test'")
    
    # Get statistics
    stats = db.get_statistics()
    print(f"Database statistics: {stats}")