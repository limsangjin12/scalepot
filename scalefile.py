from api import scale, scale_check, State, g as scaleinfo

@scale
def scale():
    print '<Scale Delegate>'
    print scaleinfo.role.name
    print scaleinfo.state
    print scaleinfo.count

@scale_check
def scale_check():
    print '<Scale Check Delegate>'
    print scaleinfo.role.name
    print scaleinfo.count
    if scaleinfo.role.name == 'worker':
        return State.MAX_LIMIT
    return State.NORMAL
