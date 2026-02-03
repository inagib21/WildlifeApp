"""Interactive chat interface for querying the system"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import logging
import re
import uuid

try:
    from ..database import get_db, Detection, Camera, ChatHistory
    from ..utils.audit import log_audit_event
    from ..services.chat_nlp import chat_nlp_service
except ImportError:
    from database import get_db, Detection, Camera, ChatHistory
    from utils.audit import log_audit_event
    from services.chat_nlp import chat_nlp_service

# Check transformers availability
try:
    import transformers
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_chat_router(limiter, get_db) -> APIRouter:
    """Setup chat router with rate limiting and dependencies"""
    
    def parse_query(query: str) -> Dict[str, Any]:
        """Parse natural language query and extract intent"""
        query_lower = query.lower().strip()
        
        # Count queries
        count_patterns = [
            (r'how many (detections|species|animals?)', 'count_detections'),
            (r'count (detections|species|animals?)', 'count_detections'),
            (r'number of (detections|species|animals?)', 'count_detections'),
            (r'total (detections|species|animals?)', 'count_detections'),
        ]
        
        # List queries
        list_patterns = [
            (r'show (me )?(all|all the)? (detections|species|animals?)', 'list_detections'),
            (r'list (detections|species|animals?)', 'list_detections'),
            (r'what (detections|species|animals?)', 'list_detections'),
        ]
        
        # Time-based queries
        time_patterns = {
            'last month': timedelta(days=30),
            'last week': timedelta(days=7),
            'last 24 hours': timedelta(hours=24),
            'last day': timedelta(days=1),
            'yesterday': timedelta(days=1),
            'today': timedelta(days=0),
            'this week': timedelta(days=7),
            'this month': timedelta(days=30),
        }
        
        # Species queries
        species_match = re.search(r'(\w+(?:\s+\w+)?)\s+(detections|sightings)', query_lower)
        species = None
        if species_match:
            species = species_match.group(1)
        
        # Camera queries
        camera_match = re.search(r'camera\s+(\d+)', query_lower)
        camera_id = None
        if camera_match:
            camera_id = int(camera_match.group(1))
        
        # Date range
        start_date = None
        for time_key, delta in time_patterns.items():
            if time_key in query_lower:
                start_date = datetime.utcnow() - delta
                break
        
        # Intent detection
        intent = 'count_detections'
        for pattern, intent_type in count_patterns:
            if re.search(pattern, query_lower):
                intent = intent_type
                break
        
        for pattern, intent_type in list_patterns:
            if re.search(pattern, query_lower):
                intent = intent_type
                break
        
        # Confidence threshold
        confidence_match = re.search(r'(?:confidence|above|over|more than)\s+([\d.]+)', query_lower)
        confidence = None
        if confidence_match:
            confidence = float(confidence_match.group(1))
            if confidence > 1.0:  # Convert percentage to decimal
                confidence = confidence / 100.0
        
        return {
            'intent': intent,
            'species': species,
            'camera_id': camera_id,
            'start_date': start_date.isoformat() if start_date else None,
            'confidence': confidence
        }
    
    def execute_query(db: Session, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parsed query and return results"""
        query = db.query(Detection)
        
        # Apply filters
        if parsed.get('species'):
            query = query.filter(Detection.species.ilike(f"%{parsed['species']}%"))
        
        if parsed.get('camera_id'):
            query = query.filter(Detection.camera_id == parsed['camera_id'])
        
        if parsed.get('start_date'):
            try:
                start_dt = datetime.fromisoformat(parsed['start_date'])
                query = query.filter(Detection.timestamp >= start_dt)
            except ValueError:
                pass
        
        if parsed.get('confidence'):
            query = query.filter(Detection.confidence >= parsed['confidence'])
        
        # Execute based on intent
        if parsed['intent'] == 'count_detections':
            count = query.count()
            
            # Get unique species count
            unique_species = query.with_entities(Detection.species).distinct().count()
            
            return {
                'type': 'count',
                'count': count,
                'unique_species': unique_species,
                'message': f"Found {count} detections" + 
                          (f" with {unique_species} unique species" if unique_species > 0 else "")
            }
        
        elif parsed['intent'] == 'list_detections':
            detections = query.order_by(Detection.timestamp.desc()).limit(50).all()
            
            return {
                'type': 'list',
                'count': len(detections),
                'data': [
                    {
                        'id': d.id,
                        'timestamp': d.timestamp.isoformat(),
                        'species': d.species,
                        'confidence': d.confidence,
                        'camera_id': d.camera_id
                    }
                    for d in detections
                ],
                'message': f"Showing {len(detections)} detections"
            }
        
        return {
            'type': 'text',
            'message': 'Query executed successfully'
        }
    
    @router.post("/api/chat/query")
    @limiter.limit("60/minute")  # Rate limit chat queries
    async def chat_query(
        request: Request,
        query: str,
        session_id: Optional[str] = Header(None, alias="X-Session-ID"),
        use_nlp: bool = True,  # Enable NLP features
        db: Session = Depends(get_db)
    ):
        """
        Process natural language query about detections with NLP support
        
        Features:
        - Natural language understanding
        - Multi-turn conversation support
        - Context awareness
        - Query suggestions
        - Natural language generation
        
        Examples:
        - "How many species were detected in the last month?"
        - "Show me all deer detections from camera 1"
        - "What was the most common animal this week?"
        - "How many detections have confidence above 0.8?"
        - "Follow up: show me more details" (uses context)
        """
        try:
            # Get or create session ID
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # Get conversation context
            conversation_context = chat_nlp_service.get_conversation_context(session_id)
            
            # Parse query (enhanced with NLP if available)
            if use_nlp and chat_nlp_service.is_available():
                # Use NLP to enhance parsing
                entities = chat_nlp_service.extract_entities(query)
                # Merge with rule-based parsing
                parsed = parse_query(query)
                parsed.update(entities)
            else:
                parsed = parse_query(query)
            
            # Use context to fill in missing information (multi-turn support)
            if conversation_context:
                # If query is vague, use context from previous queries
                if not parsed.get('species') and conversation_context.get('entities', {}).get('last_species'):
                    # Don't override, but log that we're using context
                    logger.debug(f"Using context species: {conversation_context['entities']['last_species']}")
                if not parsed.get('camera_id') and conversation_context.get('entities', {}).get('last_camera_id'):
                    logger.debug(f"Using context camera: {conversation_context['entities']['last_camera_id']}")
            
            # Execute query
            result = execute_query(db, parsed)
            
            # Generate natural language response
            if use_nlp and chat_nlp_service.is_available():
                nl_response = chat_nlp_service.generate_response(query, parsed, result)
            else:
                nl_response = result.get('message', 'Query executed successfully')
            
            # Update conversation context
            chat_nlp_service.update_conversation_context(session_id, query, result)
            
            # Get query suggestions
            conversation_history = conversation_context.get('queries', []) if conversation_context else []
            suggestions = chat_nlp_service.suggest_queries(query, [
                {"query": q, "response": r.get('message', '')}
                for q, r in zip(conversation_history[-3:], conversation_context.get('results', [])[-3:])
            ]) if conversation_context else chat_nlp_service.suggest_queries(query, [])
            
            # Save to chat history
            chat_entry = ChatHistory(
                query=query,
                response=nl_response,
                response_type=result.get('type', 'text'),
                response_data=json.dumps({
                    **result,
                    'nl_response': nl_response,
                    'suggestions': suggestions,
                    'session_id': session_id
                }),
                user_ip=request.client.host if request.client else None,
                success=True
            )
            db.add(chat_entry)
            db.commit()
            
            log_audit_event(
                db=db,
                request=request,
                action="CHAT_QUERY",
                resource_type="chat",
                details={
                    "query": query,
                    "intent": parsed.get('intent'),
                    "session_id": session_id,
                    "nlp_enabled": use_nlp and chat_nlp_service.is_available()
                }
            )
            
            return {
                "query": query,
                "result": result,
                "nl_response": nl_response,
                "suggestions": suggestions,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing chat query: {e}")
            
            # Save failed query to history
            try:
                chat_entry = ChatHistory(
                    query=query,
                    response=str(e),
                    response_type='error',
                    user_ip=request.client.host if request.client else None,
                    success=False
                )
                db.add(chat_entry)
                db.commit()
            except:
                pass
            
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/chat/history")
    async def get_chat_history(
        limit: Optional[int] = 50,
        session_id: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Get chat history (optionally filtered by session_id)"""
        query = db.query(ChatHistory)
        
        if session_id:
            # Filter by session_id if stored in response_data
            # This is a simple implementation - in production, add session_id column
            pass
        
        history = query.order_by(
            ChatHistory.timestamp.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": h.id,
                "timestamp": h.timestamp.isoformat(),
                "query": h.query,
                "response": h.response,
                "response_type": h.response_type,
                "response_data": json.loads(h.response_data) if h.response_data else None,
                "success": h.success
            }
            for h in history
        ]
    
    @router.get("/api/chat/suggestions")
    async def get_query_suggestions(
        query: Optional[str] = None,
        session_id: Optional[str] = Header(None, alias="X-Session-ID")
    ):
        """Get query suggestions based on current query and conversation context"""
        if not query:
            # Return default suggestions
            return {
                "suggestions": [
                    "How many detections today?",
                    "Show me all deer detections",
                    "What species were detected this week?",
                    "Show high confidence detections",
                    "How many detections from camera 1?"
                ]
            }
        
        # Get conversation context
        conversation_context = {}
        if session_id:
            conversation_context = chat_nlp_service.get_conversation_context(session_id)
        
        conversation_history = conversation_context.get('queries', []) if conversation_context else []
        
        suggestions = chat_nlp_service.suggest_queries(query, [
            {"query": q, "response": ""}
            for q in conversation_history[-3:]
        ])
        
        return {
            "suggestions": suggestions,
            "session_id": session_id
        }
    
    @router.get("/api/chat/context")
    async def get_conversation_context(
        session_id: str = Header(..., alias="X-Session-ID")
    ):
        """Get conversation context for a session"""
        context = chat_nlp_service.get_conversation_context(session_id)
        return {
            "session_id": session_id,
            "context": context,
            "queries_count": len(context.get('queries', [])),
            "has_context": bool(context)
        }
    
    @router.post("/api/chat/clear")
    async def clear_chat_history(
        request: Request,
        session_id: Optional[str] = Header(None, alias="X-Session-ID"),
        db: Session = Depends(get_db)
    ):
        """Clear chat history (optionally for a specific session)"""
        if session_id:
            # Clear conversation context for this session
            if session_id in chat_nlp_service.conversation_context:
                del chat_nlp_service.conversation_context[session_id]
            return {"deleted": "session_context", "session_id": session_id}
        else:
            # Clear all chat history from database
            deleted = db.query(ChatHistory).delete()
            db.commit()
            
            # Clear all conversation contexts
            chat_nlp_service.conversation_context.clear()
            
            log_audit_event(
                db=db,
                request=request,
                action="CLEAR_CHAT",
                resource_type="chat"
            )
            
            return {"deleted": deleted}
    
    @router.get("/api/chat/nlp-status")
    async def get_nlp_status():
        """Get NLP service status"""
        return {
            "available": chat_nlp_service.is_available(),
            "transformers_available": TRANSFORMERS_AVAILABLE if 'TRANSFORMERS_AVAILABLE' in globals() else False,
            "qa_model_loaded": chat_nlp_service.qa_pipeline is not None,
            "text_gen_model_loaded": chat_nlp_service.model is not None
        }
    
    return router

