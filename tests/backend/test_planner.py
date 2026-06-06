from backend.agents.planner import PlannerAgent


def test_open_chrome_routes_to_system_agent():
    plan = PlannerAgent().plan("Open Chrome")
    assert plan.agent == "system"
    assert plan.action == "launch_app"


def test_shutdown_after_requires_confirmation():
    plan = PlannerAgent().plan("Shutdown after 5 minutes")
    assert plan.agent == "scheduler"
    assert plan.requires_confirmation is True
    assert plan.params["delay_seconds"] == 300


def test_file_delete_requires_confirmation():
    plan = PlannerAgent().plan("Delete file old.txt")
    assert plan.agent == "file"
    assert plan.action == "delete_file"
    assert plan.requires_confirmation is True


def test_nightly_backup_routes_to_scheduler():
    plan = PlannerAgent().plan("Backup my project every night")
    assert plan.agent == "scheduler"
    assert plan.action == "schedule_daily"


def test_more_planner_routes():
    planner = PlannerAgent()
    assert planner.plan("Search Google for FastAPI").action == "search_google"
    assert planner.plan("Create a file called notes.txt").action == "create_file"
    assert planner.plan("Find files matching report").action == "search_files"
    assert planner.plan("Tell me how much I coded this week").action == "weekly_report"
    assert planner.plan("Restart laptop at 10 PM").action == "schedule_at"
    assert planner.plan("Move all PDFs to Documents").action == "move_by_extension"
    assert planner.plan("Find duplicate files").action == "find_duplicates"
    assert planner.plan("Show CPU status").action == "status"
    assert planner.plan("Backup this folder").action == "backup_folder"
