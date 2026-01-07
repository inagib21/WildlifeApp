"""Behavioral analysis from AI predictions"""
import logging
from typing import Dict, Any, List, Optional, Set
from collections import Counter

logger = logging.getLogger(__name__)

# Behavioral keywords that might appear in predictions
BEHAVIORAL_KEYWORDS = {
    "eating": ["eating", "feed", "feeding", "food", "foraging", "grazing", "consuming"],
    "drinking": ["drinking", "water", "drink"],
    "running": ["running", "sprint", "fleeing", "chasing"],
    "walking": ["walking", "moving", "strolling"],
    "resting": ["resting", "sleeping", "lying", "sitting", "perched"],
    "playing": ["playing", "jumping", "frolicking"],
    "grooming": ["grooming", "cleaning", "preening"],
    "alert": ["alert", "watching", "observing", "standing", "vigilant"],
    "nesting": ["nest", "nesting", "burrow", "den"],
    "mating": ["mating", "courting", "breeding"],
}

# Objects that suggest behavior
BEHAVIORAL_OBJECTS = {
    "eating": ["food", "fruit", "berry", "seed", "nut", "leaf", "grass"],
    "drinking": ["water", "pond", "stream", "bowl"],
    "nesting": ["nest", "burrow", "hole", "tree"],
    "playing": ["toy", "ball"],
}

def extract_behavioral_info(predictions: List[Dict[str, Any]], model_name: str) -> List[str]:
    """
    Extract behavioral information from predictions
    
    Args:
        predictions: List of prediction dicts with "prediction" and "prediction_score"
        model_name: Name of the model making predictions
    
    Returns:
        List of detected behaviors
    """
    behaviors = []
    prediction_texts = [p.get("prediction", "").lower() for p in predictions]
    
    # Check for behavioral keywords in predictions
    for behavior, keywords in BEHAVIORAL_KEYWORDS.items():
        for keyword in keywords:
            for pred_text in prediction_texts:
                if keyword in pred_text:
                    behaviors.append(behavior)
                    break
    
    # Check for behavioral objects
    for behavior, objects in BEHAVIORAL_OBJECTS.items():
        for obj in objects:
            for pred_text in prediction_texts:
                if obj in pred_text:
                    behaviors.append(behavior)
                    break
    
    return list(set(behaviors))  # Remove duplicates


def analyze_behavioral_consensus(all_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze behavioral information across all AI models
    
    Args:
        all_results: Results from compare_models() - dict of backend_name -> results
    
    Returns:
        Dict with behavioral analysis:
        {
            "behaviors": ["eating", "alert"],
            "consensus_behaviors": ["eating"],  # Behaviors detected by multiple models
            "unique_behaviors": {"yolov11": ["running"]},  # Behaviors only one model detected
            "confidence": {"eating": 0.8}  # Confidence scores for behaviors
        }
    """
    all_behaviors = []
    behavior_by_model = {}
    behavior_scores = {}
    
    # Extract behaviors from each model
    for model_name, result in all_results.items():
        if "error" in result or "predictions" not in result:
            continue
        
        predictions = result.get("predictions", [])
        behaviors = extract_behavioral_info(predictions, model_name)
        
        if behaviors:
            behavior_by_model[model_name] = behaviors
            all_behaviors.extend(behaviors)
            
            # Calculate confidence for behaviors based on prediction scores
            for behavior in behaviors:
                # Find the prediction that triggered this behavior
                for pred in predictions:
                    pred_text = pred.get("prediction", "").lower()
                    behavior_keywords = BEHAVIORAL_KEYWORDS.get(behavior, []) + BEHAVIORAL_OBJECTS.get(behavior, [])
                    
                    for keyword in behavior_keywords:
                        if keyword in pred_text:
                            pred_score = pred.get("prediction_score", 0.0)
                            if behavior not in behavior_scores:
                                behavior_scores[behavior] = []
                            behavior_scores[behavior].append(pred_score)
                            break
    
    # Count behavior occurrences
    behavior_counts = Counter(all_behaviors)
    
    # Consensus behaviors (detected by 2+ models)
    consensus_behaviors = [
        behavior for behavior, count in behavior_counts.items() 
        if count >= 2
    ]
    
    # Unique behaviors (only one model detected)
    unique_behaviors = {}
    for model_name, behaviors in behavior_by_model.items():
        unique = [b for b in behaviors if behavior_counts[b] == 1]
        if unique:
            unique_behaviors[model_name] = unique
    
    # Calculate average confidence for each behavior
    behavior_confidence = {}
    for behavior, scores in behavior_scores.items():
        if scores:
            behavior_confidence[behavior] = sum(scores) / len(scores)
    
    return {
        "behaviors": list(set(all_behaviors)),
        "consensus_behaviors": consensus_behaviors,
        "unique_behaviors": unique_behaviors,
        "confidence": behavior_confidence,
        "by_model": behavior_by_model
    }


def enhance_predictions_with_behavior(result: Dict[str, Any], behavioral_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance prediction results with behavioral information
    
    Args:
        result: Single model result dict
        behavioral_analysis: Full behavioral analysis from analyze_behavioral_consensus
    
    Returns:
        Enhanced result with behavioral info
    """
    model_name = result.get("name", "").lower()
    
    # Get behaviors detected by this specific model
    model_behaviors = behavioral_analysis.get("by_model", {}).get(model_name, [])
    
    # Mark which behaviors are consensus (detected by multiple models)
    consensus_behaviors = set(behavioral_analysis.get("consensus_behaviors", []))
    
    enhanced = result.copy()
    enhanced["behaviors"] = model_behaviors
    enhanced["has_behavioral_info"] = len(model_behaviors) > 0
    
    # Add behavioral confidence if available
    if model_behaviors:
        behavior_confidences = {}
        for behavior in model_behaviors:
            if behavior in behavioral_analysis.get("confidence", {}):
                behavior_confidences[behavior] = behavioral_analysis["confidence"][behavior]
            else:
                behavior_confidences[behavior] = result.get("confidence", 0.0)
        enhanced["behavior_confidence"] = behavior_confidences
    
    # Mark consensus behaviors
    enhanced["consensus_behaviors"] = [b for b in model_behaviors if b in consensus_behaviors]
    
    return enhanced

