"""
Core AI Native Tool Substrate & Auto-Registry Loader
Quadrillion Tool Matrix (QTM) - Version 0.3.0
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

def register_all_native_tools(registry: Any, state_manager: Optional[Any] = None, bus: Optional[Any] = None) -> int:
    """
    Automatically registers the complete Quadrillion Tool Matrix (QTM)
    of pre-compiled, zero-latency native tools into the provided ToolRegistry.
    """
    initial_count = len(registry.tools)

    # 1. System & Resource Tools
    from tools.native.system_tools import (
        get_time, time_schema,
        get_system_status, system_status_schema,
        inspect_system_resources, system_resources_schema,
        factory_reset, factory_reset_schema,
        get_disk_usage, disk_usage_schema,
        get_battery_status, battery_status_schema,
        get_network_interfaces, network_interfaces_schema
    )
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, system_status_schema)
    registry.register_tool("inspect_system_resources", inspect_system_resources, system_resources_schema)
    registry.register_tool("factory_reset", factory_reset, factory_reset_schema)
    registry.register_tool("get_disk_usage", get_disk_usage, disk_usage_schema)
    registry.register_tool("get_battery_status", get_battery_status, battery_status_schema)
    registry.register_tool("get_network_interfaces", get_network_interfaces, network_interfaces_schema)

    # 2. File & Storage Tools
    from tools.native.file_tools import (
        read_text_file, read_file_schema,
        write_text_file, write_file_schema,
        list_dir_contents, list_dir_schema
    )
    registry.register_tool("read_text_file", read_text_file, read_file_schema)
    registry.register_tool("write_text_file", write_text_file, write_file_schema)
    registry.register_tool("list_dir_contents", list_dir_contents, list_dir_schema)

    # 3. Math & Numbers Tools
    from tools.native.math_tools import (
        calculate_math, calculate_math_schema,
        summarize_numbers, summarize_numbers_schema
    )
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    registry.register_tool("summarize_numbers", summarize_numbers, summarize_numbers_schema)

    # 4. Knowledge & Fact Tools
    from tools.native.knowledge_tools import lookup_knowledge, knowledge_schema
    registry.register_tool("lookup_knowledge", lookup_knowledge, knowledge_schema)

    # 5. Weather Tools
    from tools.native.weather_tools import get_weather, weather_schema
    registry.register_tool("get_weather", get_weather, weather_schema)

    # 6. Web & Browser Tools
    from tools.native.web_tools import (
        open_url, open_url_schema,
        search_web_query, search_web_query_schema,
        open_youtube, open_youtube_schema,
        fetch_url_text, fetch_url_text_schema,
        http_request_json, http_request_json_schema,
        download_file, download_file_schema
    )
    registry.register_tool("open_url", open_url, open_url_schema)
    registry.register_tool("search_web_query", search_web_query, search_web_query_schema)
    registry.register_tool("open_youtube", open_youtube, open_youtube_schema)
    registry.register_tool("fetch_url_text", fetch_url_text, fetch_url_text_schema)
    registry.register_tool("http_request_json", http_request_json, http_request_json_schema)
    registry.register_tool("download_file", download_file, download_file_schema)

    # 7. Desktop & OS Control Tools
    from tools.native.desktop_tools import (
        launch_application, launch_application_schema,
        open_path_in_explorer, open_path_in_explorer_schema,
        take_screenshot, take_screenshot_schema,
        get_clipboard_text, get_clipboard_text_schema,
        set_clipboard_text, set_clipboard_text_schema
    )
    registry.register_tool("launch_application", launch_application, launch_application_schema)
    registry.register_tool("open_path_in_explorer", open_path_in_explorer, open_path_in_explorer_schema)
    registry.register_tool("take_screenshot", take_screenshot, take_screenshot_schema)
    registry.register_tool("get_clipboard_text", get_clipboard_text, get_clipboard_text_schema)
    registry.register_tool("set_clipboard_text", set_clipboard_text, set_clipboard_text_schema)

    # 8. Media & Audio Tools
    from tools.native.media_tools import (
        media_control, media_control_schema,
        set_system_volume, set_volume_schema,
        toggle_audio_mute, toggle_mute_schema,
        get_audio_devices, audio_devices_schema
    )
    registry.register_tool("media_control", media_control, media_control_schema)
    registry.register_tool("set_system_volume", set_system_volume, set_volume_schema)
    registry.register_tool("toggle_audio_mute", toggle_audio_mute, toggle_mute_schema)
    registry.register_tool("get_audio_devices", get_audio_devices, audio_devices_schema)

    # 9. Process & Hardware Supervisor Tools
    from tools.native.process_tools import (
        list_running_processes, list_running_processes_schema,
        kill_process, kill_process_schema,
        get_hardware_metrics, get_hardware_metrics_schema,
        lock_workstation, lock_workstation_schema
    )
    registry.register_tool("list_running_processes", list_running_processes, list_running_processes_schema)
    registry.register_tool("kill_process", kill_process, kill_process_schema)
    registry.register_tool("get_hardware_metrics", get_hardware_metrics, get_hardware_metrics_schema)
    registry.register_tool("lock_workstation", lock_workstation, lock_workstation_schema)

    # 10. Shell Command Execution Tool
    from tools.native.shell_tools import run_shell_command, run_shell_command_schema
    registry.register_tool("run_shell_command", run_shell_command, run_shell_command_schema)

    # 11. Developer & Workspace Tools
    from tools.native.dev_tools import (
        get_git_status, get_git_status_schema,
        manage_notes, manage_notes_schema,
        git_diff_summary, git_diff_schema,
        git_commit_changes, git_commit_schema,
        compute_file_hash, file_hash_schema,
        find_files_by_pattern, find_files_schema,
        read_json_file, read_json_schema,
        write_json_file, write_json_schema,
        set_state_manager as set_dev_sm
    )
    if state_manager:
        set_dev_sm(state_manager)
    registry.register_tool("get_git_status", get_git_status, get_git_status_schema)
    registry.register_tool("manage_notes", manage_notes, manage_notes_schema)
    registry.register_tool("git_diff_summary", git_diff_summary, git_diff_schema)
    registry.register_tool("git_commit_changes", git_commit_changes, git_commit_schema)
    registry.register_tool("compute_file_hash", compute_file_hash, file_hash_schema)
    registry.register_tool("find_files_by_pattern", find_files_by_pattern, find_files_schema)
    registry.register_tool("read_json_file", read_json_file, read_json_schema)
    registry.register_tool("write_json_file", write_json_file, write_json_schema)

    # 12. Network & LAN Tools
    from tools.native.network_tools import (
        scan_local_network, scan_local_network_schema,
        inspect_lan_device, inspect_lan_device_schema,
        ping_host, ping_host_schema,
        check_port_open, check_port_schema,
        get_public_ip, public_ip_schema,
        dns_lookup, dns_lookup_schema,
        wake_on_lan, wake_on_lan_schema
    )
    registry.register_tool("scan_local_network", scan_local_network, scan_local_network_schema)
    registry.register_tool("inspect_lan_device", inspect_lan_device, inspect_lan_device_schema)
    registry.register_tool("ping_host", ping_host, ping_host_schema)
    registry.register_tool("check_port_open", check_port_open, check_port_schema)
    registry.register_tool("get_public_ip", get_public_ip, public_ip_schema)
    registry.register_tool("dns_lookup", dns_lookup, dns_lookup_schema)
    registry.register_tool("wake_on_lan", wake_on_lan, wake_on_lan_schema)

    # 13. Calendar & Anticipation Tools
    from tools.native.calendar_tools import (
        manage_calendar, manage_calendar_schema,
        reconcile_schedule_evidence, reconcile_schedule_evidence_schema,
        get_upcoming_schedule, get_upcoming_schedule_schema,
        set_state_manager as set_cal_sm
    )
    if state_manager:
        set_cal_sm(state_manager)
    registry.register_tool("manage_calendar", manage_calendar, manage_calendar_schema)
    registry.register_tool("reconcile_schedule_evidence", reconcile_schedule_evidence, reconcile_schedule_evidence_schema)
    registry.register_tool("get_upcoming_schedule", get_upcoming_schedule, get_upcoming_schedule_schema)

    # 14. Proactive Rule Management Tools
    from tools.native.proactive_tools import (
        create_reminder, create_reminder_schema,
        create_vitals_watcher, create_vitals_watcher_schema,
        list_active_rules, list_active_rules_schema,
        cancel_proactive_rule, cancel_proactive_rule_schema,
        set_state_manager as set_proactive_sm
    )
    if state_manager:
        set_proactive_sm(state_manager)
    registry.register_tool("create_reminder", create_reminder, create_reminder_schema)
    registry.register_tool("create_vitals_watcher", create_vitals_watcher, create_vitals_watcher_schema)
    registry.register_tool("list_active_rules", list_active_rules, list_active_rules_schema)
    registry.register_tool("cancel_proactive_rule", cancel_proactive_rule, cancel_proactive_rule_schema)

    added_count = len(registry.tools) - initial_count
    logger.info(f"[QTM] Registered {added_count} native tools into registry (Total available: {len(registry.tools)})")
    return added_count
