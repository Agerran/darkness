def establish_call(caller_device, callee_number):
    outbound_call = caller_device.start_call(callee_number)
    outbound_call.expect_answer(15)

    return outbound_call

def establish_call_between(caller_device, callee_number, callee_device):
    outbound_call = caller_device.start_call(callee_number)
    inbound_call = callee_device.expect_incoming_call(15)
    inbound_call.pickup()

    outbound_call.expect_answer(15)

    return (outbound_call, inbound_call)
