from .crossbar import Crossbar
from .sup import Sup
import psycopg2
import time

def su_cb(environment, **kwargs) -> Crossbar:
    return Crossbar(environment['crossbar_url'], **environment['credentials']['superadmin'], **kwargs)

def admin_cb(environment, **kwargs) -> Crossbar:
    return Crossbar(environment['crossbar_url'], **environment['credentials']['admin'], **kwargs)

def user_cb(environment, **kwargs) -> Crossbar:
    return Crossbar(environment['crossbar_url'], **environment['credentials']['user'], **kwargs)

def build_sup(environment, **kwargs):
    return Sup(environment['sup'])

def make_internal_call(extension_1, extension_2, call_length=5, time_to_answer=5):
    (extension_1_device, _extension_1_number) = extension_1
    (extension_2_device, extension_2_number) = extension_2

    with (
        extension_1_device.start_call(extension_2_number) as outbound_call,
        extension_2_device.expect_incoming_call(15) as inbound_call
        ):
            time.sleep(time_to_answer)
            inbound_call.pickup()

            time.sleep(call_length)
            outbound_call.hangup()

            inbound_call.expect_disconnect()
            outbound_call.expect_disconnect()

            return (outbound_call, inbound_call)

def find_callflow_id_by_number(account_cb: Crossbar, number):
    for callflow in account_cb['callflows'].get({'paginate': False}):
        if number in callflow.numbers:
            return callflow.id

    raise Exception('Callflow not found')



def set_callflow_id_in_callflow(callflow, new_callflow_id):
    if callflow.module == 'callflow':
        callflow.data.id = new_callflow_id
        return callflow
    else:
        for key in callflow.children:
            callflow.children[key] = set_callflow_id_in_callflow(callflow.children[key], new_callflow_id)

    return callflow

def link_callflow_to_another(inbound_number, extension_number, admin_cb):
    inbound_callflow = None
    extension_callflow = None

    extension_callflow_id = find_callflow_id_by_number(admin_cb['accounts'][admin_cb.account_id], extension_number)
    inbound_callflow_id = find_callflow_id_by_number(admin_cb['accounts'][admin_cb.account_id], inbound_number)
    inbound_callflow = admin_cb['accounts'][admin_cb.account_id]['callflows'][inbound_callflow_id]

    if not inbound_callflow:
        raise Exception("Cannot find callflow for inbound_route")

    inbound_callflow.data.flow = set_callflow_id_in_callflow(inbound_callflow.data.flow, extension_callflow_id)
    inbound_callflow.save()

def peek_one_or_many(items, n=1):
    if n == 1:
        return items[0]
    else:
        return items[:n]
