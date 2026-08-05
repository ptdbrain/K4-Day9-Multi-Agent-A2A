import os
import json
import argparse
from tqdm import tqdm
from data_loader import OlistDatabase
from agents import CoordinatorAgent

def run_pipeline(ticket_id=None):
    # Khởi tạo data
    db = OlistDatabase("data")
    coordinator = CoordinatorAgent(db)

    # Đảm bảo thư mục output tồn tại
    os.makedirs("output", exist_ok=True)

    input_dir = "input"
    output_dir = "output"
    
    if ticket_id:
        tickets = [f"{ticket_id}.json"]
    else:
        # Lấy tất cả các file JSON trong input/
        tickets = sorted([f for f in os.listdir(input_dir) if f.endswith(".json")])

    trace_logs = []

    print(f"Processing {len(tickets)} tickets...")
    for t_file in tqdm(tickets, desc="Processing Tickets"):
        t_path = os.path.join(input_dir, t_file)
        with open(t_path, "r", encoding="utf-8") as f:
            ticket_data = json.load(f)
        
        case_id = ticket_data.get("case_id")
        
        # Xử lý ticket bằng Coordinator
        final_json, trace = coordinator.process_ticket(ticket_data)
        
        # Ghi kết quả output/
        out_path = os.path.join(output_dir, f"{case_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, ensure_ascii=False, indent=2)
            
        trace_logs.append(trace)

    # Ghi trace.jsonl ra root repo
    with open("trace.jsonl", "w", encoding="utf-8") as f:
        for log in trace_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
            
    # Ghi bản copy vào logging/ nếu thư mục đó tồn tại
    if os.path.exists("logging"):
        with open("logging/trace.jsonl", "w", encoding="utf-8") as f:
            for log in trace_logs:
                f.write(json.dumps(log, ensure_ascii=False) + "\n")

    print("Pipeline run completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Multi-Agent Dispute Resolution Pipeline")
    parser.add_argument("--ticket", type=str, default=None, help="Specific Ticket ID to run (e.g. EC_001)")
    args = parser.parse_args()
    
    run_pipeline(args.ticket)
