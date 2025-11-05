from server.modules.data.store import RESULTS

def get_result(order_id: str) -> dict:
    return RESULTS.get(order_id, {"status":"unknown","order_id":order_id})

def list_results() -> dict:
    return RESULTS
