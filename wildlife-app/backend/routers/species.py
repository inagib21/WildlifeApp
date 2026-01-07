"""Species information endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Optional, Dict, Any
import logging

try:
    from ..services.species_info import species_info_service
except ImportError:
    from services.species_info import species_info_service

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_species_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup species router with rate limiting and dependencies"""
    
    @router.get("/api/species")
    @limiter.limit("60/minute")
    def get_all_species(request):
        """Get information for all species"""
        try:
            species = species_info_service.get_all_species()
            return {
                "count": len(species),
                "species": species
            }
        except Exception as e:
            logger.error(f"Error getting all species: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving species information: {str(e)}")
    
    @router.get("/api/species/{species_name}")
    @limiter.limit("60/minute")
    def get_species_info(species_name: str, request):
        """Get detailed information for a specific species"""
        try:
            info = species_info_service.get_species_info(species_name)
            if not info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Species information not found for: {species_name}"
                )
            return info
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting species info for {species_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving species information: {str(e)}")
    
    @router.get("/api/species/search")
    @limiter.limit("60/minute")
    def search_species(
        q: str = Query(..., description="Search query"),
        request = None
    ):
        """Search species by name, scientific name, or description"""
        try:
            results = species_info_service.search_species(q)
            return {
                "query": q,
                "count": len(results),
                "results": results
            }
        except Exception as e:
            logger.error(f"Error searching species: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error searching species: {str(e)}")
    
    return router

