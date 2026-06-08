from fastapi import APIRouter

router = APIRouter()


@router.get("/fixtures")
async def list_fixtures() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Fixture listing — Phase 2"}


@router.get("/odds/{fixture_id}")
async def get_fixture_odds(fixture_id: str) -> dict[str, str]:
    return {"status": "not_implemented", "fixture_id": fixture_id}


@router.get("/predictions/{fixture_id}")
async def get_predictions(fixture_id: str) -> dict[str, str]:
    return {"status": "not_implemented", "fixture_id": fixture_id}


@router.get("/ev-opportunities")
async def list_ev_opportunities() -> dict[str, str]:
    return {"status": "not_implemented", "message": "+EV scan — Phase 2"}
