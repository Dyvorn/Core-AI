import os
import sqlite3
import json
import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from core.schemas import PipelinePlan, PipelineStep, UserProfile, DeviceTopologyRecord, ProactiveTriggerRule, ZoneRecord, AudioRouteRecord


logger = logging.getLogger(__name__)


class StateManager:
    """Manages SQLite state including WAL-mode for high concurrency, pipeline states, and audit logs"""
    
    def __init__(self, db_path: str = "core_ai.db"):
        if db_path == ":memory:":
            import uuid
            self.db_path = f"file:mem_{uuid.uuid4().hex}?mode=memory&cache=shared"
            self._is_uri = True
            self._anchor_conn = sqlite3.connect(self.db_path, uri=True, check_same_thread=False)
        else:
            self.db_path = db_path
            self._is_uri = False
            self._anchor_conn = None
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, uri=self._is_uri, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # 1. Pipelines
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pipelines (
                    id TEXT PRIMARY KEY,
                    goal TEXT,
                    status TEXT,
                    plan_data JSON,
                    result JSON,
                    error_summary TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')
            
            # 2. Key-Value State
            conn.execute('''
                CREATE TABLE IF NOT EXISTS kv_state (
                    key TEXT PRIMARY KEY,
                    value JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. Room & Zone State
            conn.execute('''
                CREATE TABLE IF NOT EXISTS room_state (
                    room_id TEXT PRIMARY KEY,
                    state JSON,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')


            # 4. Pipeline Steps
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pipeline_steps (
                    pipeline_id TEXT,
                    step_id TEXT,
                    name TEXT,
                    tool_name TEXT,
                    status TEXT,
                    inputs JSON,
                    outputs JSON,
                    error TEXT,
                    duration_ms REAL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    PRIMARY KEY (pipeline_id, step_id)
                )
            ''')

            # 5. Dynamic Tools
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dynamic_tools (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    file_path TEXT,
                    schema JSON,
                    is_verified INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 6. Execution Audit Logs
            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_id TEXT,
                    step_id TEXT,
                    level TEXT,
                    source TEXT,
                    message TEXT,
                    payload JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 7. User Profiles (Identity, Nickname, Persona Preferences)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    preferred_name TEXT,
                    aliases JSON,
                    pronouns TEXT,
                    preferred_tone TEXT,
                    preferences JSON,
                    updated_at TIMESTAMP
                )
            ''')
            try:
                conn.execute("ALTER TABLE user_profiles ADD COLUMN aliases JSON")
            except Exception:
                pass

            # 8. Dynamic Spatial Zones (Created on demand as the user adds rooms or spaces)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS zones (
                    zone_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            ''')

            # 9. Device Topology (Fixed spatial anchors vs. Roaming devices)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS device_topology (
                    device_id TEXT PRIMARY KEY,
                    name TEXT,
                    device_type TEXT,
                    is_fixed_anchor INTEGER DEFAULT 0,
                    current_zone TEXT,
                    nearest_anchor_id TEXT,
                    capabilities JSON,
                    last_seen TIMESTAMP,
                    metadata JSON
                )
            ''')

            # 10. Proactive Trigger Rules
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proactive_rules (
                    rule_id TEXT PRIMARY KEY,
                    name TEXT,
                    condition_type TEXT,
                    trigger_condition JSON,
                    action_goal TEXT,
                    target_zone TEXT,
                    priority TEXT DEFAULT 'normal',
                    is_active INTEGER DEFAULT 1,
                    cooldown_seconds INTEGER DEFAULT 300,
                    last_triggered_at TIMESTAMP
                )
            ''')

            # 11. Spatial Audio Routes (Dynamically binds spatial zones to audio interfaces)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audio_routes (
                    zone_id TEXT PRIMARY KEY,
                    input_device_name TEXT,
                    output_device_name TEXT,
                    input_device_index INTEGER,
                    output_device_index INTEGER,
                    preferred_volume REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1,
                    metadata JSON,
                    updated_at TIMESTAMP
                )
            ''')

            # 12. Mesh Offline Execution Queue
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mesh_offline_queue (
                    id TEXT PRIMARY KEY,
                    goal TEXT,
                    context JSON,
                    result JSON,
                    status TEXT,
                    created_at TIMESTAMP,
                    synced INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            self._run_migrations(conn)
            logger.info("Database initialized successfully with pipeline, profile, dynamic zones, topology, audio routing, mesh offline queue, and migrations.")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
        finally:
            conn.close()

    def _run_migrations(self, conn: sqlite3.Connection):
        """
        Manages sequential zero-downtime database schema upgrades over time.
        Tracks version via PRAGMA user_version.
        """
        cursor = conn.execute("PRAGMA user_version")
        row = cursor.fetchone()
        current_version = row[0] if row else 0

        if current_version < 1:
            conn.execute("PRAGMA user_version = 1")
            current_version = 1

        if current_version < 2:
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_logs_source ON execution_logs(source)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_device_topology_zone ON device_topology(current_zone)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_steps_pipeline_id ON pipeline_steps(pipeline_id)")
                conn.execute("PRAGMA user_version = 2")
                logger.info("Database schema migration v2 applied successfully.")
            except Exception as me:
                logger.warning(f"Notice during migration v2: {me}")

        if current_version < 3:
            try:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS mesh_offline_queue (
                        id TEXT PRIMARY KEY,
                        goal TEXT,
                        context JSON,
                        result JSON,
                        status TEXT,
                        created_at TIMESTAMP,
                        synced INTEGER DEFAULT 0
                    )
                ''')
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mesh_offline_synced ON mesh_offline_queue(synced)")
                conn.execute("PRAGMA user_version = 3")
                logger.info("Database schema migration v3 applied successfully.")
            except Exception as me:
                logger.warning(f"Notice during migration v3: {me}")
        conn.commit()

    def get_schema_version(self) -> int:
        """Returns the current PRAGMA user_version of the database."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("PRAGMA user_version")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def create_backup(self, backup_dir: str = "backups") -> Optional[str]:
        """Creates a timestamped point-in-time snapshot using the lock-free SQLite online backup API."""
        if self._is_uri or self.db_path == ":memory:":
            return None
        if not os.path.exists(self.db_path):
            return None
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"state_backup_{timestamp}.db")
        source_conn = self._get_connection()
        try:
            dest_conn = sqlite3.connect(backup_file)
            source_conn.backup(dest_conn)
            dest_conn.close()
            logger.info(f"Database point-in-time snapshot created at: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Failed to create database snapshot: {e}")
            return None
        finally:
            source_conn.close()

    # Room State methods
    def set_room_state(self, room_id: str, state_data: Dict[str, Any]):
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO room_state (room_id, state, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (room_id, json.dumps(state_data))
            )
            conn.commit()
        finally:
            conn.close()

    def get_room_state(self, room_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT state FROM room_state WHERE room_id = ?", (room_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row['state'])
            return None
        finally:
            conn.close()

    # Pipeline State methods
    def save_pipeline(self, plan: PipelinePlan):
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            plan_json = plan.model_dump_json()
            conn.execute('''
                INSERT OR REPLACE INTO pipelines 
                (id, goal, status, plan_data, result, error_summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                plan.id,
                plan.goal,
                plan.status,
                plan_json,
                json.dumps(plan.final_output) if plan.final_output is not None else None,
                plan.error_summary,
                plan.created_at.isoformat() if plan.created_at else now_iso,
                now_iso
            ))
            
            # Save individual steps
            for step in plan.steps:
                self.save_step(plan.id, step, conn)

            conn.commit()
        finally:
            conn.close()

    def update_pipeline_status(self, pipeline_id: str, status: str, final_output: Any = None, error_summary: Optional[str] = None):
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                UPDATE pipelines
                SET status = ?, result = ?, error_summary = ?, updated_at = ?
                WHERE id = ?
            ''', (
                status,
                json.dumps(final_output) if final_output is not None else None,
                error_summary,
                now_iso,
                pipeline_id
            ))
            conn.commit()
        finally:
            conn.close()

    def save_step(self, pipeline_id: str, step: PipelineStep, existing_conn=None):
        should_close = False
        conn = existing_conn
        if conn is None:
            conn = self._get_connection()
            should_close = True
        try:
            conn.execute('''
                INSERT OR REPLACE INTO pipeline_steps
                (pipeline_id, step_id, name, tool_name, status, inputs, outputs, error, duration_ms, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pipeline_id,
                step.id,
                step.name,
                step.tool_name,
                step.status,
                json.dumps(step.arguments),
                json.dumps(step.output) if step.output is not None else None,
                step.error,
                step.duration_ms,
                step.started_at.isoformat() if step.started_at else None,
                step.completed_at.isoformat() if step.completed_at else None
            ))
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
            row = cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            if result.get("plan_data"):
                result["plan_data"] = json.loads(result["plan_data"])
            if result.get("result"):
                result["result"] = json.loads(result["result"])
            return result
        finally:
            conn.close()

    # Dynamic Tools Catalog
    def register_dynamic_tool_record(self, name: str, description: str, file_path: str, schema: dict, is_verified: bool = True):
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO dynamic_tools
                (name, description, file_path, schema, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (name, description, file_path, json.dumps(schema), 1 if is_verified else 0))
            conn.commit()
        finally:
            conn.close()

    def get_dynamic_tool_records(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM dynamic_tools")
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                item["schema"] = json.loads(item["schema"]) if item.get("schema") else {}
                results.append(item)
            return results
        finally:
            conn.close()

    # Execution Logs
    def log_execution(self, source: str, level: str, message: str, pipeline_id: Optional[str] = None, step_id: Optional[str] = None, payload: Optional[dict] = None):
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT INTO execution_logs (pipeline_id, step_id, level, source, message, payload)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                pipeline_id,
                step_id,
                level,
                source,
                message,
                json.dumps(payload, default=str) if payload else None
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to record execution log in DB: {e}")
        finally:
            conn.close()

    def get_recent_execution_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM execution_logs ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in reversed(rows):
                item = dict(row)
                item["payload"] = json.loads(item["payload"]) if item.get("payload") else None
                results.append(item)
            return results
        finally:
            conn.close()


    # --- User Profile & Identity Memory ---
    def get_user_profile(self, user_id: str = "primary_user") -> UserProfile:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["aliases"] = json.loads(data["aliases"]) if data.get("aliases") else []
                data["preferences"] = json.loads(data["preferences"]) if data.get("preferences") else {}
                if data.get("updated_at") and isinstance(data["updated_at"], str):
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                return UserProfile(**data)
            # Default profile: neutral blank-slate for open-source deployment
            default_profile = UserProfile(user_id=user_id, preferred_name="User", aliases=[])
            self.save_user_profile(default_profile)
            return default_profile
        finally:
            conn.close()

    def save_user_profile(self, profile: UserProfile):
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT OR REPLACE INTO user_profiles
                (user_id, preferred_name, aliases, pronouns, preferred_tone, preferences, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile.user_id,
                profile.preferred_name,
                json.dumps(profile.aliases),
                profile.pronouns,
                profile.preferred_tone,
                json.dumps(profile.preferences),
                now_iso
            ))
            conn.commit()
            logger.info(f"Updated user profile for '{profile.user_id}': preferred_name='{profile.preferred_name}'")
        finally:
            conn.close()

    def set_user_preferred_name(
        self,
        preferred_name: str,
        aliases: Optional[List[str]] = None,
        user_id: str = "primary_user",
        alias: Optional[str] = None
    ) -> UserProfile:
        """Sets the operator's preferred name and optional aliases/alias."""
        profile = self.get_user_profile(user_id)
        profile.preferred_name = preferred_name
        if aliases is not None:
            profile.aliases = aliases
        elif alias is not None:
            profile.aliases = [alias]
        profile.updated_at = datetime.now(timezone.utc)
        self.save_user_profile(profile)
        return profile

    # --- Dynamic Spatial Zones (Zero Hardcoding) ---
    def ensure_zone_exists(self, zone_id: str, display_name: Optional[str] = None, metadata: Optional[dict] = None) -> ZoneRecord:
        """Ensures a spatial zone is registered dynamically on-the-fly without hardcoded assumptions."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
                if data.get("created_at") and isinstance(data["created_at"], str):
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                return ZoneRecord(**data)
            
            # Create dynamically on-demand
            name = display_name or zone_id.replace("_", " ").title()
            now_iso = datetime.now(timezone.utc).isoformat()
            meta_json = json.dumps(metadata or {})
            conn.execute('''
                INSERT INTO zones (zone_id, display_name, created_at, metadata)
                VALUES (?, ?, ?, ?)
            ''', (zone_id, name, now_iso, meta_json))
            conn.commit()
            logger.info(f"Dynamically provisioned new spatial zone: '{zone_id}' ('{name}')")
            return ZoneRecord(zone_id=zone_id, display_name=name, metadata=metadata or {})
        finally:
            conn.close()

    def list_zones(self) -> List[ZoneRecord]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM zones")
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
                if data.get("created_at") and isinstance(data["created_at"], str):
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                results.append(ZoneRecord(**data))
            return results
        finally:
            conn.close()

    def delete_zone(self, zone_id: str) -> bool:
        """Deletes a spatial zone from the database."""
        clean_id = zone_id.strip().lower()
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM zones WHERE LOWER(zone_id) = ?", (clean_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted spatial zone: '{clean_id}'")
            return deleted
        finally:
            conn.close()

    def delete_all_zones_except(self, keep_zone_ids: List[str]) -> List[str]:
        """Deletes all spatial zones except the specified keep list."""
        clean_keeps = [k.strip().lower() for k in keep_zone_ids if k.strip()]
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT zone_id FROM zones")
            all_zones = [row[0] for row in cursor.fetchall()]
            to_delete = [z for z in all_zones if z.lower() not in clean_keeps]
            for zid in to_delete:
                conn.execute("DELETE FROM zones WHERE zone_id = ?", (zid,))
            conn.commit()
            if to_delete:
                logger.info(f"Deleted spatial zones: {to_delete}. Preserved: {clean_keeps}")
            return to_delete
        finally:
            conn.close()

    # --- Device Topology (Fixed vs. Roaming Devices) ---
    def register_or_update_device(self, record: DeviceTopologyRecord):
        conn = self._get_connection()
        try:
            if record.current_zone:
                self.ensure_zone_exists(record.current_zone)

            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT OR REPLACE INTO device_topology
                (device_id, name, device_type, is_fixed_anchor, current_zone, nearest_anchor_id, capabilities, last_seen, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.device_id,
                record.name,
                record.device_type,
                1 if record.is_fixed_anchor else 0,
                record.current_zone,
                record.nearest_anchor_id,
                json.dumps(record.capabilities),
                now_iso,
                json.dumps(record.metadata)
            ))
            conn.commit()
            logger.info(f"Updated device topology for '{record.device_id}' ({'Fixed Anchor' if record.is_fixed_anchor else 'Roaming'} in '{record.current_zone}')")
        finally:
            conn.close()

    def get_device_record(self, device_id: str) -> Optional[DeviceTopologyRecord]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM device_topology WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["is_fixed_anchor"] = bool(data["is_fixed_anchor"])
            data["capabilities"] = json.loads(data["capabilities"]) if data.get("capabilities") else []
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            if data.get("last_seen") and isinstance(data["last_seen"], str):
                data["last_seen"] = datetime.fromisoformat(data["last_seen"])
            return DeviceTopologyRecord(**data)
        finally:
            conn.close()

    def list_all_devices(self) -> List[DeviceTopologyRecord]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM device_topology")
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data["is_fixed_anchor"] = bool(data["is_fixed_anchor"])
                data["capabilities"] = json.loads(data["capabilities"]) if data.get("capabilities") else []
                data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
                if data.get("last_seen") and isinstance(data["last_seen"], str):
                    data["last_seen"] = datetime.fromisoformat(data["last_seen"])
                results.append(DeviceTopologyRecord(**data))
            return results
        finally:
            conn.close()

    def update_device_zone(self, device_id: str, zone: str, nearest_anchor_id: Optional[str] = None):
        self.ensure_zone_exists(zone)
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                UPDATE device_topology
                SET current_zone = ?, nearest_anchor_id = ?, last_seen = ?
                WHERE device_id = ?
            ''', (zone, nearest_anchor_id, now_iso, device_id))
            conn.commit()
            logger.info(f"Relocated device '{device_id}' to zone '{zone}' (anchor={nearest_anchor_id})")
        finally:
            conn.close()


    # --- Proactive Trigger Rules ---
    def save_proactive_rule(self, rule: ProactiveTriggerRule):
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO proactive_rules
                (rule_id, name, condition_type, trigger_condition, action_goal, target_zone, priority, is_active, cooldown_seconds, last_triggered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.rule_id,
                rule.name,
                rule.condition_type,
                json.dumps(rule.trigger_condition),
                rule.action_goal,
                rule.target_zone,
                rule.priority,
                1 if rule.is_active else 0,
                rule.cooldown_seconds,
                rule.last_triggered_at.isoformat() if rule.last_triggered_at else None
            ))
            conn.commit()
            logger.info(f"Saved proactive rule '{rule.name}' ({rule.rule_id[:8]})")
        finally:
            conn.close()

    register_proactive_rule = save_proactive_rule

    def get_active_proactive_rules(self) -> List[ProactiveTriggerRule]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM proactive_rules WHERE is_active = 1")
            rules = []
            for row in cursor.fetchall():
                data = dict(row)
                data["trigger_condition"] = json.loads(data["trigger_condition"]) if data.get("trigger_condition") else {}
                data["is_active"] = bool(data["is_active"])
                if data.get("last_triggered_at") and isinstance(data["last_triggered_at"], str):
                    data["last_triggered_at"] = datetime.fromisoformat(data["last_triggered_at"])
                rules.append(ProactiveTriggerRule(**data))
            return rules
        finally:
            conn.close()

    def update_rule_last_triggered(self, rule_id: str):
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                UPDATE proactive_rules
                SET last_triggered_at = ?
                WHERE rule_id = ?
            ''', (now_iso, rule_id))
            conn.commit()
        finally:
            conn.close()

    def deactivate_proactive_rule(self, rule_id: str):
        """Marks a proactive rule as inactive (useful for one-shot countdowns and reminders)."""
        conn = self._get_connection()
        try:
            conn.execute('''
                UPDATE proactive_rules
                SET is_active = 0
                WHERE rule_id = ?
            ''', (rule_id,))
            conn.commit()
            logger.info(f"Deactivated proactive rule {rule_id[:8]}")
        finally:
            conn.close()

    def delete_proactive_rule(self, rule_id_or_name: str) -> bool:
        """Permanently deletes a proactive rule or reminder by ID or matching name."""
        conn = self._get_connection()
        try:
            cursor = conn.execute('''
                DELETE FROM proactive_rules
                WHERE rule_id = ? OR LOWER(name) = LOWER(?) OR LOWER(name) LIKE ?
            ''', (rule_id_or_name, rule_id_or_name, f"%{rule_id_or_name.lower()}%"))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_all_proactive_rules(self) -> List[ProactiveTriggerRule]:
        """Returns all configured proactive rules, including inactive ones."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM proactive_rules ORDER BY is_active DESC, name ASC")
            rules = []
            for row in cursor.fetchall():
                data = dict(row)
                data["trigger_condition"] = json.loads(data["trigger_condition"]) if data.get("trigger_condition") else {}
                data["is_active"] = bool(data["is_active"])
                if data.get("last_triggered_at") and isinstance(data["last_triggered_at"], str):
                    data["last_triggered_at"] = datetime.fromisoformat(data["last_triggered_at"])
                rules.append(ProactiveTriggerRule(**data))
            return rules
        finally:
            conn.close()

    # --- Generic Persistent Key-Value & Notes Memory ---
    def set_kv(self, key: str, value: Any):
        """Persists an arbitrary JSON-serializable value to SQLite kv_state table."""
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT OR REPLACE INTO kv_state (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, json.dumps(value), now_iso))
            conn.commit()
        finally:
            conn.close()

    def get_kv(self, key: str, default: Any = None) -> Any:
        """Retrieves an arbitrary value from kv_state table."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT value FROM kv_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return default
        finally:
            conn.close()

    def list_kv(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """Lists key-value pairs matching an optional prefix."""
        conn = self._get_connection()
        try:
            if prefix:
                cursor = conn.execute("SELECT key, value FROM kv_state WHERE key LIKE ?", (f"{prefix}%",))
            else:
                cursor = conn.execute("SELECT key, value FROM kv_state")
            out = {}
            for row in cursor.fetchall():
                out[row[0]] = json.loads(row[1]) if row[1] else None
            return out
        finally:
            conn.close()

    def delete_kv(self, key: str) -> bool:
        """Deletes a key from kv_state."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM kv_state WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


    # --- Dynamic Spatial Audio Routes ---
    def get_audio_route(self, zone_id: str) -> Optional[AudioRouteRecord]:
        """Fetches the active audio hardware routing record for an arbitrary spatial zone."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM audio_routes WHERE zone_id = ?", (zone_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["is_active"] = bool(data["is_active"])
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            if data.get("updated_at") and isinstance(data["updated_at"], str):
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])
            return AudioRouteRecord(**data)
        finally:
            conn.close()

    def set_audio_route(self, route: AudioRouteRecord):
        """Binds a spatial zone to specific hardware or network audio interfaces with zero hardcoding."""
        self.ensure_zone_exists(route.zone_id)
        conn = self._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT OR REPLACE INTO audio_routes
                (zone_id, input_device_name, output_device_name, input_device_index, output_device_index, preferred_volume, is_active, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                route.zone_id,
                route.input_device_name,
                route.output_device_name,
                route.input_device_index,
                route.output_device_index,
                route.preferred_volume,
                1 if route.is_active else 0,
                json.dumps(route.metadata),
                now_iso
            ))
            conn.commit()
            logger.info(f"Updated audio route for zone '{route.zone_id}' (in='{route.input_device_name}', out='{route.output_device_name}')")
        finally:
            conn.close()

    def list_all_audio_routes(self) -> List[AudioRouteRecord]:
        """Lists all configured zone-to-audio hardware bindings."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM audio_routes")
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data["is_active"] = bool(data["is_active"])
                data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
                if data.get("updated_at") and isinstance(data["updated_at"], str):
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                results.append(AudioRouteRecord(**data))
            return results
        finally:
            conn.close()

    def delete_audio_route(self, zone_id: str):
        """Removes an audio route binding for a zone."""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM audio_routes WHERE zone_id = ?", (zone_id,))
            conn.commit()
            logger.info(f"Deleted audio route for zone '{zone_id}'")
        finally:
            conn.close()

    # --- Phase 5: Mesh Offline Execution Queue & Bidirectional Synchronization ---

    def enqueue_offline_task(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        status: str = "completed_locally"
    ) -> str:
        """Stores an offline executed task into durable SQLite queue for later synchronization."""
        task_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT INTO mesh_offline_queue (id, goal, context, result, status, created_at, synced)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (
                task_id,
                goal,
                json.dumps(context or {}),
                json.dumps(result or {}, default=str),
                status,
                now_iso
            ))
            conn.commit()
            logger.info(f"Enqueued offline task '{task_id[:8]}' for mesh synchronization.")
            return task_id
        finally:
            conn.close()

    def get_unsynced_offline_tasks(self) -> List[Dict[str, Any]]:
        """Retrieves all offline tasks pending synchronization with the central server."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM mesh_offline_queue WHERE synced = 0 ORDER BY created_at ASC")
            tasks = []
            for row in cursor.fetchall():
                d = dict(row)
                d["context"] = json.loads(d["context"]) if d.get("context") else {}
                d["result"] = json.loads(d["result"]) if d.get("result") else {}
                tasks.append(d)
            return tasks
        finally:
            conn.close()

    def mark_offline_tasks_synced(self, task_ids: List[str]) -> int:
        """Marks offline tasks as successfully synchronized."""
        if not task_ids:
            return 0
        conn = self._get_connection()
        try:
            placeholders = ",".join("?" for _ in task_ids)
            cursor = conn.execute(f"UPDATE mesh_offline_queue SET synced = 1 WHERE id IN ({placeholders})", task_ids)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_kv_with_metadata(self, prefix: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves kv_state records with keys, values, and updated_at timestamps, optionally filtered."""
        conn = self._get_connection()
        try:
            query = "SELECT key, value, updated_at FROM kv_state"
            params = []
            clauses = []
            if prefix:
                clauses.append("key LIKE ?")
                params.append(f"{prefix}%")
            if since:
                clauses.append("updated_at > ?")
                params.append(since)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            cursor = conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                results.append({
                    "key": row[0],
                    "value": json.loads(row[1]) if row[1] else None,
                    "updated_at": row[2]
                })
            return results
        finally:
            conn.close()

    def merge_kv_records(self, records: List[Dict[str, Any]]) -> int:
        """Merges a list of KV records into local kv_state. Last-write-wins based on updated_at."""
        if not records:
            return 0
        merged = 0
        conn = self._get_connection()
        try:
            for r in records:
                k = r.get("key")
                v = r.get("value")
                new_ts = r.get("updated_at") or datetime.now(timezone.utc).isoformat()
                if not k:
                    continue
                cursor = conn.execute("SELECT updated_at FROM kv_state WHERE key = ?", (k,))
                row = cursor.fetchone()
                should_update = True
                if row and row[0]:
                    existing_ts = row[0]
                    if existing_ts > new_ts:
                        should_update = False
                if should_update:
                    conn.execute('''
                        INSERT OR REPLACE INTO kv_state (key, value, updated_at)
                        VALUES (?, ?, ?)
                    ''', (k, json.dumps(v), new_ts))
                    merged += 1
            conn.commit()
            return merged
        finally:
            conn.close()

    def merge_zones(self, zones: List[Dict[str, Any]]) -> int:
        """Merges spatial zone definitions."""
        count = 0
        for z in zones:
            zid = z.get("zone_id")
            if zid:
                self.ensure_zone_exists(
                    zone_id=zid,
                    display_name=z.get("display_name"),
                    metadata=z.get("metadata")
                )
                count += 1
        return count

    def merge_devices(self, devices: List[Dict[str, Any]]) -> int:
        """Merges device topology records."""
        count = 0
        for d in devices:
            if not d.get("device_id"):
                continue
            rec_dict = dict(d)
            if isinstance(rec_dict.get("last_seen"), str):
                rec_dict["last_seen"] = datetime.fromisoformat(rec_dict["last_seen"])
            rec = DeviceTopologyRecord(**rec_dict)
            self.register_or_update_device(rec)
            count += 1
        return count

    def merge_proactive_rules(self, rules: List[Dict[str, Any]]) -> int:
        """Merges proactive trigger rules."""
        count = 0
        for r in rules:
            if not r.get("rule_id") or not r.get("name"):
                continue
            r_dict = dict(r)
            if isinstance(r_dict.get("last_triggered_at"), str):
                r_dict["last_triggered_at"] = datetime.fromisoformat(r_dict["last_triggered_at"])
            rule = ProactiveTriggerRule(**r_dict)
            self.save_proactive_rule(rule)
            count += 1
        return count

    def merge_audio_routes(self, routes: List[Dict[str, Any]]) -> int:
        """Merges spatial audio routing configurations."""
        count = 0
        for r in routes:
            if not r.get("zone_id"):
                continue
            r_dict = dict(r)
            if isinstance(r_dict.get("updated_at"), str):
                r_dict["updated_at"] = datetime.fromisoformat(r_dict["updated_at"])
            self.set_audio_route(AudioRouteRecord(**r_dict))
            count += 1
        return count

    def get_state_deltas(
        self,
        since: Optional[str] = None,
        entities: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extracts all state entities matching requested criteria for delta synchronization."""
        targets = set(entities or ["profile", "kv_state", "zones", "devices", "proactive_rules", "audio_routes", "dynamic_tools"])
        deltas: Dict[str, Any] = {
            "timestamp": time.time(),
            "profile": None,
            "kv_state": [],
            "zones": [],
            "devices": [],
            "proactive_rules": [],
            "audio_routes": [],
            "dynamic_tools": [],
            "offline_tasks": []
        }

        if "profile" in targets:
            prof = self.get_user_profile()
            deltas["profile"] = prof.model_dump(mode="json")

        if "kv_state" in targets:
            deltas["kv_state"] = self.get_kv_with_metadata(since=since)

        if "zones" in targets:
            deltas["zones"] = [z.model_dump(mode="json") for z in self.list_zones()]

        if "devices" in targets:
            deltas["devices"] = [d.model_dump(mode="json") for d in self.list_all_devices()]

        if "proactive_rules" in targets:
            deltas["proactive_rules"] = [r.model_dump(mode="json") for r in self.get_all_proactive_rules()]

        if "audio_routes" in targets:
            deltas["audio_routes"] = [a.model_dump(mode="json") for a in self.list_all_audio_routes()]

        if "dynamic_tools" in targets:
            deltas["dynamic_tools"] = self.get_dynamic_tool_records()

        return deltas

    def merge_state_deltas(self, deltas: Dict[str, Any]) -> Dict[str, int]:
        """Applies incoming delta payload from another node and returns merged item counts."""
        counts = {
            "profile": 0,
            "kv_state": 0,
            "zones": 0,
            "devices": 0,
            "proactive_rules": 0,
            "audio_routes": 0,
            "offline_tasks": 0
        }

        # 1. Profile merge
        p_data = deltas.get("profile")
        if p_data and isinstance(p_data, dict):
            existing_prof = self.get_user_profile()
            in_name = p_data.get("preferred_name")
            is_incoming_custom = in_name not in ("User", "Operator", None, "")
            is_existing_custom = existing_prof.preferred_name not in ("User", "Operator", None, "")

            in_updated = p_data.get("updated_at")
            if isinstance(in_updated, str):
                in_updated_dt = datetime.fromisoformat(in_updated)
            else:
                in_updated_dt = in_updated

            should_save = False
            if not is_incoming_custom and is_existing_custom:
                # Never overwrite a custom operator profile with a blank-slate default
                should_save = False
            elif is_incoming_custom and not is_existing_custom:
                # Promote to custom operator profile
                should_save = True
            elif in_updated_dt and existing_prof.updated_at and in_updated_dt > existing_prof.updated_at:
                should_save = True
            elif in_updated_dt and not existing_prof.updated_at:
                should_save = True

            if should_save:
                p_data["updated_at"] = in_updated_dt
                self.save_user_profile(UserProfile(**p_data))
                counts["profile"] = 1

        # 2. KV state
        if deltas.get("kv_state"):
            counts["kv_state"] = self.merge_kv_records(deltas["kv_state"])

        # 3. Zones
        if deltas.get("zones"):
            counts["zones"] = self.merge_zones(deltas["zones"])

        # 4. Devices
        if deltas.get("devices"):
            counts["devices"] = self.merge_devices(deltas["devices"])

        # 5. Proactive rules
        if deltas.get("proactive_rules"):
            counts["proactive_rules"] = self.merge_proactive_rules(deltas["proactive_rules"])

        # 6. Audio routes
        if deltas.get("audio_routes"):
            counts["audio_routes"] = self.merge_audio_routes(deltas["audio_routes"])

        # 7. Offline tasks merge (for server receiving from edge nodes)
        tasks = deltas.get("offline_tasks", [])
        for t in tasks:
            if isinstance(t, dict):
                self.log_execution(
                    source=f"edge_offline:{t.get('source_node', 'roaming')}",
                    level="INFO",
                    message=f"Synced offline task: {t.get('goal')}",
                    payload={"context": t.get("context"), "result": t.get("result"), "offline_id": t.get("id")}
                )
                counts["offline_tasks"] += 1

        return counts



