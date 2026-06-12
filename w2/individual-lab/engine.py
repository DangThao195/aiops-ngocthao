import argparse
import json
import yaml
import os
from features import extract_live_features
from retrieval import find_similar_precedents
from decision import select_best_action

def main():
    parser = argparse.ArgumentParser(description="Evidence-Driven Remediation Engine")
    parser.add_argument("--incident", required=True, help="Path to live incident JSON")
    parser.add_argument("--history", required=True, help="Path to history JSON")
    parser.add_argument("--actions", required=True, help="Path to actions YAML")
    args = parser.parse_args()

    with open(args.incident, 'r', encoding='utf-8') as f:
        live_incident = json.load(f)
    with open(args.history, 'r', encoding='utf-8') as f:
        history_corpus = json.load(f)
    with open(args.actions, 'r', encoding='utf-8') as f:
        action_catalog = yaml.safe_load(f)

    incident_id = os.path.basename(args.incident).split('.')[0]

    live_features = extract_live_features(live_incident)
    retrieval_output = find_similar_precedents(live_features, history_corpus)
    decision = select_best_action(retrieval_output, action_catalog, live_features, live_incident)

    output_doc = {
        "incident_id": incident_id,
        "selected_action": decision["name"],
        "params": decision["params"],
        "confidence": round(decision["confidence"], 2),
        "evidence": {
            "top_historical_matches": decision["matches"],
            "derived_affected_services": live_features["affected_services"],
            "ood_flag": decision["is_ood"],
            "ev_calculation": decision["ev_details"],
            "extracted_drain_templates": list(live_features["log_signatures"])
        }
    }

    print(json.dumps(output_doc, indent=2))

    with open("audit.jsonl", "a", encoding='utf-8') as audit_file:
        audit_file.write(json.dumps(output_doc, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()