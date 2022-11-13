import traceback

class RenderError(Exception):
    def __init__(self, message="", stack=None, show_stack=False):
        self.message = message
        if stack and isinstance(stack, Exception):
            self.stack = getattr(stack, 'stack', None)
        elif stack and type(stack) in (str, str):
            self.stack = stack
        else:
            self.stack = None
        if not self.stack:
            self.stack = "".join(traceback.format_stack(None, 6)[:-1])

        if show_stack:
            self.message += '\n\tSTACK\t: %s' % self.stack.rstrip().replace("\n", "\n\t\t: ")
            
    def __str__(self):
        return "Render Error: %s" % (self.message)


class ValidateError(Exception):
    def __init__(self, message="", stack=None):
        self.message = message
        if stack and isinstance(stack, Exception):
            self.stack = getattr(stack, 'stack', None)
        elif stack and type(stack) in (str, str):
            self.stack = stack
        else:
            self.stack = None
        if not self.stack:
            self.stack = "".join(traceback.format_stack(None, 6)[:-1])

    def __str__(self):
        return "Validate Error: %s" % (self.message)

class CmdError(Exception):
    def __init__(self, retval=0, message="", cmd=None, stack=None):
        self.retval = retval
        self.message = message
        self.cmd = cmd
        if stack and isinstance(stack, Exception):
            self.stack = getattr(stack, 'stack', None)
        elif stack and type(stack) in (str, str):
            self.stack = stack
        else:
            self.stack = None
        if not self.stack:
            self.stack = "".join(traceback.format_stack(None, 6)[:-1])

    def __str__(self):
        if not self.cmd:
            cmdstr = ""
        elif type(self.cmd) in (list, tuple):
            cmdstr = "CMD: " + " ".join(((' ' in x and "'"+x+"'" or x) for x in self.cmd))
        else:
            cmdstr = "CMD: " + str(self.cmd)
        if self.message:
            message = "\n\tOUTPUT\t: %s" % self.message.strip().replace("\n","\n\t\t: ")
        else:
            message = ""
        return "EXIT: %d  %s%s" % (self.retval, cmdstr, message)
