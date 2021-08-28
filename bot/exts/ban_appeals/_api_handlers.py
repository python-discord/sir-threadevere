from aiohttp import ClientSession

from bot import constants, logger
from bot.exts.ban_appeals import _models


async def fetch_form_appeal_data(response_uuid: str, cookies: dict, session: ClientSession) -> _models.AppealDetails:
    """Fetches ban appeal data from the pydis forms API."""
    logger.info(f"Fetching appeal info for form response {response_uuid}")
    url = f"{constants.URLs.forms}/forms/ban-appeals/responses/{response_uuid}"
    async with session.get(url, cookies=cookies, raise_for_status=True) as resp:
        appeal_response_data = await resp.json()
        appealer = f"{appeal_response_data['user']['username']}#{appeal_response_data['user']['discriminator']}"
        return _models.AppealDetails(
            appealer=appealer,
            uuid=appeal_response_data["id"],
            email=appeal_response_data["user"]["email"],
            reason=appeal_response_data["response"]["reason"],
            justification=appeal_response_data["response"]["justification"]
        )


async def post_appeal_respose_email(email_body: str, appealer_email: str) -> None:
    """Sends the appeal response email to the appealer."""
    # Awaiting new mail provider before we implement this.
    raise NotImplementedError
