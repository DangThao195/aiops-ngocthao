import math

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        except ImportError:
            raise ImportError("Vui lòng cài đặt thư viện hỗ trợ bằng lệnh: pip install sentence-transformers")
    return _embedding_model

def calculate_cosine_similarity(vec_a, vec_b):
    dot_product = sum(p * q for p, q in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(p * p for p in vec_a))
    norm_b = math.sqrt(sum(q * q for q in vec_b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def calculate_semantic_log_similarity(live_logs, hist_logs):
    if not live_logs or not hist_logs:
        return 0.0
        
    model = _get_embedding_model()

    live_list = list(live_logs)
    hist_list = list(hist_logs)

    live_embeddings = model.encode(live_list, convert_to_numpy=False)
    hist_embeddings = model.encode(hist_list, convert_to_numpy=False)

    total_score = 0.0
    for live_vec in live_embeddings:
        max_sim = 0.0
        for hist_vec in hist_embeddings:
            sim = calculate_cosine_similarity(live_vec, hist_vec)
            if sim > max_sim:
                max_sim = sim
        total_score += max_sim

    return float(total_score / len(live_embeddings))

def calculate_trace_similarity(live_traces, hist_traces):
    if not live_traces or not hist_traces:
        return 0.0
    
    hist_trace_dict = {}
    for ht in hist_traces:
        edge = (ht["from"], ht["to"])
        hist_trace_dict[edge] = ht

    matched_edges = 0
    total_score = 0.0
    
    for edge, live_metrics in live_traces.items():
        if live_metrics["error_rate"] > 0.05 or live_metrics["p99_deviation_ratio"] > 1.5:
            if edge in hist_trace_dict:
                matched_edges += 1
                hist_metrics = hist_trace_dict[edge]
                
                error_diff = abs(live_metrics["error_rate"] - hist_metrics.get("error_rate", 0.0))
                error_score = max(0.0, 1.0 - error_diff)
                
                live_dev = live_metrics["p99_deviation_ratio"]
                hist_dev = hist_metrics.get("p99_deviation_ratio", 1.0)
                dev_ratio = min(live_dev, hist_dev) / max(live_dev, hist_dev) if max(live_dev, hist_dev) > 0 else 1.0
                
                total_score += (error_score * 0.5 + dev_ratio * 0.5)
                
    if matched_edges == 0:
        return 0.0
    return total_score / matched_edges

def parse_historical_action(action_str):
    parts = action_str.split(":")
    action_name = parts[0]
    params = {}
    
    if action_name == "rollback_service" and len(parts) >= 2:
        params["service"] = parts[1]
        params["target_version"] = "previous"
    elif action_name == "increase_pool_size" and len(parts) >= 2:
        params["service"] = parts[1]
        if len(parts) >= 3 and "->" in parts[2]:
            p_parts = parts[2].split("->")
            params["from_value"] = p_parts[0]
            params["to_value"] = p_parts[1]
    elif action_name in ["restart_pod", "restart_service"] and len(parts) >= 2:
        params["service"] = parts[1]
        params["pod_selector"] = "all"
    elif action_name in ["dns_config_rollback", "network_policy_revert"] and len(parts) >= 2:
        params["configmap_name"] = parts[1]
        if len(parts) >= 3:
            params["target_revision"] = parts[2]
            
    return {"name": action_name, "params": params}

def find_similar_precedents(live_features, history_corpus):
    action_votes = {}
    top_matches = []
    
    live_logs = live_features["log_signatures"]
    live_traces = live_features["trace_signatures"]
    live_affected = set(live_features["affected_services"])
    
    for hist_entry in history_corpus:
        hist_logs = set(hist_entry.get("log_signatures", []))
        log_sim = calculate_semantic_log_similarity(live_logs, hist_logs)
        
        hist_traces = hist_entry.get("trace_signatures", [])
        trace_sim = calculate_trace_similarity(live_traces, hist_traces)
        
        hist_affected = set(hist_entry.get("affected_services", []))
        affected_sim = calculate_jaccard_similarity_set(live_affected, hist_affected)

        hybrid_score = (log_sim * 0.5) + (trace_sim * 0.3) + (affected_sim * 0.2)

        hybrid_score_float = float(hybrid_score)
        
        if hybrid_score_float > 0.4: 
            top_matches.append({
                "id": hist_entry["id"],
                "score": round(hybrid_score_float, 4),
                "root_cause_class": hist_entry["root_cause_class"]
            })
            
            outcome = hist_entry.get("outcome", "success").lower()
            if outcome == "success":
                weight = 1.0
            elif outcome == "partial":
                weight = 0.5
            else:
                weight = -1.0
                
            for act_str in hist_entry.get("actions_taken", []):
                parsed_act = parse_historical_action(act_str)
                act_key = (parsed_act["name"], frozenset(parsed_act["params"].items()))
                
                vote_increment = hybrid_score * weight
                
                if act_key not in action_votes:
                    action_votes[act_key] = {
                        "name": parsed_act["name"],
                        "params": parsed_act["params"],
                        "accumulated_score": 0.0,
                        "success_count": 0,
                        "fail_count": 0
                    }
                    
                action_votes[act_key]["accumulated_score"] += vote_increment
                if outcome == "success":
                    action_votes[act_key]["success_count"] += 1
                elif outcome == "failed":
                    action_votes[act_key]["fail_count"] += 1

    top_matches = sorted(top_matches, key=lambda x: x["score"], reverse=True)[:3]
    
    ranked_candidates = []
    for act_key, act_data in action_votes.items():
        if act_data["accumulated_score"] > 0:
            ranked_candidates.append({
                "name": act_data["name"],
                "params": act_data["params"],
                "score": round(act_data["accumulated_score"], 4),
                "success_count": act_data["success_count"],
                "fail_count": act_data["fail_count"]
            })
            
    ranked_candidates = sorted(ranked_candidates, key=lambda x: x["score"], reverse=True)
    
    return {
        "candidates": ranked_candidates,
        "top_matches": top_matches
    }

def calculate_jaccard_similarity_set(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))