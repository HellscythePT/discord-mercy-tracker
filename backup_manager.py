"""Backup and recovery management for user data"""

import json
import os
import shutil
from datetime import datetime
import logging
from config import BACKUP_FOLDER, MAX_BACKUPS, DATA_FILE

logger = logging.getLogger(__name__)

def ensure_backup_folder():
    """Ensure backup folder exists"""
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)
        logger.info(f"Created backup folder: {BACKUP_FOLDER}")

def backup_data(data):
    """Create a backup of user data"""
    try:
        ensure_backup_folder()
        
        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"user_data_backup_{timestamp}.json"
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
        
        # Save backup
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"Created backup: {backup_filename}")
        
        # Clean up old backups
        cleanup_old_backups()
        
        return backup_path
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def cleanup_old_backups():
    """Remove old backup files, keeping only the most recent MAX_BACKUPS"""
    try:
        if not os.path.exists(BACKUP_FOLDER):
            return
        
        # Get all backup files
        backup_files = [f for f in os.listdir(BACKUP_FOLDER) if f.startswith("user_data_backup_")]
        
        if len(backup_files) <= MAX_BACKUPS:
            return
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_FOLDER, x)), reverse=True)
        
        # Remove excess backups
        files_to_remove = backup_files[MAX_BACKUPS:]
        for filename in files_to_remove:
            file_path = os.path.join(BACKUP_FOLDER, filename)
            os.remove(file_path)
            logger.info(f"Removed old backup: {filename}")
            
    except Exception as e:
        logger.error(f"Error cleaning up backups: {e}")

def restore_data():
    """Restore data from the most recent backup"""
    try:
        ensure_backup_folder()
        
        # Get all backup files
        backup_files = [f for f in os.listdir(BACKUP_FOLDER) if f.startswith("user_data_backup_")]
        
        if not backup_files:
            logger.warning("No backup files found")
            return None
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_FOLDER, x)), reverse=True)
        
        # Load the most recent backup
        latest_backup = backup_files[0]
        backup_path = os.path.join(BACKUP_FOLDER, latest_backup)
        
        with open(backup_path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Restored data from backup: {latest_backup}")
        return data
        
    except Exception as e:
        logger.error(f"Error restoring from backup: {e}")
        return None

def restore_from_specific_backup(backup_filename):
    """Restore data from a specific backup file"""
    try:
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
        
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_filename}")
            return None
        
        with open(backup_path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Restored data from specific backup: {backup_filename}")
        return data
        
    except Exception as e:
        logger.error(f"Error restoring from specific backup {backup_filename}: {e}")
        return None

def list_backups():
    """List all available backup files"""
    try:
        ensure_backup_folder()
        
        backup_files = [f for f in os.listdir(BACKUP_FOLDER) if f.startswith("user_data_backup_")]
        
        if not backup_files:
            return []
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_FOLDER, x)), reverse=True)
        
        backup_info = []
        for filename in backup_files:
            file_path = os.path.join(BACKUP_FOLDER, filename)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            file_size = os.path.getsize(file_path)
            
            backup_info.append({
                "filename": filename,
                "modified": mod_time,
                "size": file_size
            })
        
        return backup_info
        
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []

def create_manual_backup(data, suffix="manual"):
    """Create a manual backup with custom suffix"""
    try:
        ensure_backup_folder()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"user_data_backup_{timestamp}_{suffix}.json"
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
        
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"Created manual backup: {backup_filename}")
        return backup_path
        
    except Exception as e:
        logger.error(f"Error creating manual backup: {e}")
        return None

def verify_backup_integrity(backup_filename):
    """Verify that a backup file is valid JSON and contains expected structure"""
    try:
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
        
        if not os.path.exists(backup_path):
            return False, "Backup file not found"
        
        with open(backup_path, 'r') as f:
            data = json.load(f)
        
        # Basic structure validation
        if not isinstance(data, dict):
            return False, "Invalid data structure - not a dictionary"
        
        # Check if all user IDs are valid strings
        for user_id, user_data in data.items():
            if not isinstance(user_id, str):
                return False, f"Invalid user ID format: {user_id}"
            
            if not isinstance(user_data, dict):
                return False, f"Invalid user data structure for user {user_id}"
        
        return True, "Backup integrity verified"
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {e}"
    except Exception as e:
        return False, f"Error verifying backup: {e}"
