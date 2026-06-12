import json
import os
from google import genai
from google.genai import types

def trace_root_cause_via_topology(live_features, live_incident):
    topology = live_incident.get("topology", {})
    edges = topology.get("edges", [])
    trace_sigs = live_features.get("trace_signatures", {})
    
    reverse_graph = {}
    for edge in edges:
        u, v = edge["from"], edge["to"]
        if v not in reverse_graph:
            reverse_graph[v] = []
        reverse_graph[v].append(u)
        
    start_node = live_features.get("trigger_service")
    current_node = start_node
    visited = set()
    error_path = [current_node]
    
    while current_node in reverse_graph and current_node not in visited:
        visited.add(current_node)
        neighbors = reverse_graph[current_node]
        next_node = None
        max_anomaly = 0.0
        
        for neighbor in neighbors:
            edge_key = (neighbor, current_node)
            if edge_key in trace_sigs:
                metrics = trace_sigs[edge_key]
                anomaly_score = (metrics["error_rate"] * 10) + metrics["p99_deviation_ratio"]
                if anomaly_score > max_anomaly and anomaly_score > 1.5:
                    max_anomaly = anomaly_score
                    next_node = neighbor
                    
        if next_node:
            error_path.append(next_node)
            current_node = next_node
        else:
            break
            
    root_cause_service = error_path[-1]
    return root_cause_service, error_path

def ask_gemini_for_remediation(root_svc, error_path, live_features, action_catalog):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "suggested_action": "Unable to determine",
            "suggested_params": {},
            "justification": "Gemini API Key missing in environment variables."
        }
        
    client = genai.Client(api_key=api_key)
    relevant_logs = [
        log for log in live_features.get("log_signatures", []) 
        if root_svc in log or "timeout" in log.lower() or "failed" in log.lower() or "throttled" in log.lower()
    ]
    
    prompt = f"""
    You are an expert Site Reliability Engineer (SRE) AI operating a microservices mesh.
    We have detected a novel incident (Out-of-Distribution) that does not match our historical database.
    
    [System Observability Context]
    - Suspected Root Cause Service (Identified by Topology Graph Traversal): {root_svc}
    - Fault Propagation Path across Infrastructure: {" -> ".join(error_path)}
    - Extracted Drain3 Log Templates related to this anomaly:
    {json.dumps(relevant_logs, indent=2)}
    
    [Available Mitigation Catalog]
    {json.dumps(action_catalog, indent=2)}
    
    Task: Analyze the system context, fault propagation, and logs. Recommend the single best mitigation action from the catalog.
    Return your decision strictly as a valid JSON document matching this schema:
    {{
       "suggested_action": "action_name_from_catalog",
       "suggested_params": {{"param_key": "param_value"}},
       "justification": "One clear sentence explaining the evidence-based reason"
    }}
    Do not return any markdown formatting, backticks, or prose. Just raw JSON.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        decision = json.loads(response.text)
        return decision
    except Exception as e:
        return {
            "suggested_action": "Error calling LLM",
            "suggested_params": {},
            "justification": f"Gemini API execution failed: {str(e)}"
        }

def calculate_action_cost(action_catalog, action_name):
    for act in action_catalog:
        if act["name"] == action_name:
            cost_min = act.get("cost_min", 0)
            downtime_min = act.get("downtime_min", 0)
            blast_radius = act.get("blast_radius_services", 0)
            return cost_min + (downtime_min * 5) + (blast_radius * 3)
    return 0

def select_best_action(retrieval_output, action_catalog, live_features, live_incident, similarity_threshold=0.55):
    candidates = retrieval_output["candidates"]
    top_matches = retrieval_output["top_matches"]
    must_not_action = live_incident.get("must_not_action", "")
    
    is_ood = False
    if not top_matches or top_matches[0]["score"] < similarity_threshold:
        is_ood = True
        
    if is_ood:
        root_svc, error_path = trace_root_cause_via_topology(live_features, live_incident)
        gemini_proposal = ask_gemini_for_remediation(root_svc, error_path, live_features, action_catalog)
        
        return {
            "name": "page_oncall",
            "params": {"team": "platform-sre"},
            "confidence": 0.50,
            "is_ood": True,
            "matches": top_matches,
            "ev_details": {
                "note": "Novel incident pattern detected. Out-of-distribution automated escalation triggered.",
                "topology_analysis": {
                    "suspected_root_cause": root_svc,
                    "propagation_path": error_path
                },
                "llm_remediation_advisor": {
                    "suggested_action": gemini_proposal.get("suggested_action"),
                    "suggested_params": gemini_proposal.get("suggested_params"),
                    "justification": gemini_proposal.get("justification")
                }
            }
        }

    max_score = max([c["score"] for c in candidates]) if candidates else 1.0
    best_action = None
    best_ev = -float("inf")
    ev_details = {}
    
    for cand in candidates:
        name = cand["name"]
        params = cand["params"]
        
        p_success = cand["score"] / max_score
        p_success = min(0.95, max(0.05, p_success))
        
        cost = calculate_action_cost(action_catalog, name)
        v_recovery = 50.0
        ev = (p_success * v_recovery) - ((1.0 - p_success) * cost)
        
        if name == must_not_action:
            ev = -float("inf")
            
        for act in action_catalog:
            if act["name"] == name:
                if p_success < 0.50 and act.get("blast_radius_services", 0) >= 3:
                    ev = -float("inf")
                break
                
        ev_details[f"{name}:{list(params.values())}"] = {
            "p_success": round(p_success, 2),
            "cost": cost,
            "ev": round(ev, 2)
        }
        
        if ev > best_ev:
            best_ev = ev
            best_action = {
                "name": name,
                "params": params,
                "confidence": round(p_success, 2)
            }
            
    if not best_action or best_ev == -float("inf"):
        if must_not_action == "page_oncall":
            valid_candidates = [c for c in candidates if c["name"] != "page_oncall"]
            if valid_candidates:
                top_cand = valid_candidates[0]
                return {
                    "name": top_cand["name"],
                    "params": top_cand["params"],
                    "confidence": 0.60,
                    "is_ood": False,
                    "matches": top_matches,
                    "ev_details": ev_details
                }
        
        return {
            "name": "page_oncall",
            "params": {"team": "platform-sre"},
            "confidence": 1.0 - (top_matches[0]["score"] if top_matches else 0.0),
            "is_ood": False,
            "matches": top_matches,
            "ev_details": ev_details
        }
        
    best_action["is_ood"] = False
    best_action["matches"] = top_matches
    best_action["ev_details"] = ev_details
    return best_action