"""NLP service for chat interface using Hugging Face models"""
import logging
from typing import Dict, Any, Optional, List, Tuple
import json

logger = logging.getLogger(__name__)

# Try to import transformers for NLP
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available - NLP features will be limited")


class ChatNLPService:
    """NLP service for natural language understanding and generation"""
    
    def __init__(self):
        self.qa_pipeline = None
        self.text_generator = None
        self.tokenizer = None
        self.model = None
        self.conversation_context = {}  # Store conversation context per user/session
        self.available = False
        self._try_load_models()
    
    def _try_load_models(self):
        """Try to load NLP models from Hugging Face"""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("transformers not installed - using rule-based parsing")
            return
        
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Load question answering model (lighter, faster)
            try:
                # Use a smaller, faster model for QA
                self.qa_pipeline = pipeline(
                    "question-answering",
                    model="distilbert-base-uncased-distilled-squad",
                    device=0 if device == "cuda" else -1
                )
                logger.info("Question answering model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load QA model: {e}")
            
            # Load text generation model for better responses
            try:
                # Use a smaller conversational model
                model_name = "microsoft/DialoGPT-small"  # Lighter than medium/large
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForCausalLM.from_pretrained(model_name)
                if device == "cuda":
                    self.model = self.model.to(device)
                self.text_generator = None  # Will use model directly
                logger.info("Text generation model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load text generation model: {e}")
            
            self.available = True
            
        except Exception as e:
            logger.warning(f"Failed to load NLP models: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Check if NLP models are available"""
        return self.available and TRANSFORMERS_AVAILABLE
    
    def extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities from query using NLP"""
        if not self.is_available():
            return {}
        
        # Use pattern matching as fallback
        # In production, use NER model or spaCy
        entities = {
            'species': None,
            'camera_id': None,
            'time_range': None,
            'confidence': None
        }
        
        return entities
    
    def generate_response(self, query: str, context: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Generate natural language response using NLP model"""
        if not self.is_available() or not self.model:
            # Fallback to template-based generation
            return self._generate_template_response(query, result)
        
        try:
            # Build context for generation
            context_text = self._build_context_text(context, result)
            
            # Prepare prompt
            if context_text:
                prompt = f"User: {query}\nContext: {context_text}\nAssistant:"
            else:
                prompt = f"User: {query}\nAssistant:"
            
            # Generate response
            inputs = self.tokenizer.encode(prompt, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = inputs.to("cuda")
            
            outputs = self.model.generate(
                inputs,
                max_length=150,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Extract just the assistant's response
            if "Assistant:" in response:
                response = response.split("Assistant:")[-1].strip()
            
            return response or self._generate_template_response(query, result)
            
        except Exception as e:
            logger.warning(f"Error generating NLP response: {e}")
            return self._generate_template_response(query, result)
    
    def _build_context_text(self, context: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build context text from query context and results"""
        parts = []
        
        if context.get('species'):
            parts.append(f"Species: {context['species']}")
        if context.get('camera_id'):
            parts.append(f"Camera ID: {context['camera_id']}")
        if context.get('start_date'):
            parts.append(f"Time range: {context['start_date']}")
        if result.get('count'):
            parts.append(f"Found {result['count']} detections")
        if result.get('unique_species'):
            parts.append(f"Unique species: {result['unique_species']}")
        
        return ", ".join(parts)
    
    def _generate_template_response(self, query: str, result: Dict[str, Any]) -> str:
        """Generate template-based response as fallback"""
        if result.get('type') == 'count':
            count = result.get('count', 0)
            species = result.get('unique_species', 0)
            
            if count == 0:
                return "I didn't find any detections matching your query."
            elif count == 1:
                return f"I found 1 detection with {species} unique species."
            else:
                return f"I found {count} detections with {species} unique species."
        
        elif result.get('type') == 'list':
            count = result.get('count', 0)
            if count == 0:
                return "I didn't find any detections matching your query."
            else:
                return f"Here are {count} detections matching your query."
        
        return "I've processed your query and found the results above."
    
    def suggest_queries(self, query: str, conversation_history: List[Dict[str, str]]) -> List[str]:
        """Suggest related queries based on current query and history"""
        suggestions = []
        
        # Extract common patterns
        if "how many" in query.lower() or "count" in query.lower():
            suggestions.extend([
                "Show me all detections",
                "What species were detected?",
                "Show detections from last week"
            ])
        
        if "show" in query.lower() or "list" in query.lower():
            suggestions.extend([
                "How many total detections?",
                "What's the most common species?",
                "Show high confidence detections"
            ])
        
        if "species" in query.lower() or "animal" in query.lower():
            suggestions.extend([
                "Show all detections",
                "What cameras have the most detections?",
                "Show recent detections"
            ])
        
        # Add time-based suggestions
        suggestions.extend([
            "Show detections from last 24 hours",
            "What was detected this week?",
            "Show high confidence detections"
        ])
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def get_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get conversation context for a session"""
        return self.conversation_context.get(session_id, {})
    
    def update_conversation_context(self, session_id: str, query: str, result: Dict[str, Any]):
        """Update conversation context with new query and result"""
        if session_id not in self.conversation_context:
            self.conversation_context[session_id] = {
                'queries': [],
                'results': [],
                'entities': {}
            }
        
        context = self.conversation_context[session_id]
        context['queries'].append(query)
        context['results'].append(result)
        
        # Update entities from query and result
        if result.get('species'):
            context['entities']['last_species'] = result['species']
        if result.get('camera_id'):
            context['entities']['last_camera_id'] = result['camera_id']
        
        # Keep only last 10 queries/results
        context['queries'] = context['queries'][-10:]
        context['results'] = context['results'][-10:]


# Global NLP service instance
chat_nlp_service = ChatNLPService()

