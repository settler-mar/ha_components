from datetime import datetime
import inspect


def log_print(*msg):
  frame = inspect.stack()[1]
  filename = frame.filename.split('/')[-1]
  if filename == '__init__.py':
    filename = frame.filename.split('/')[-2] + '/'
  lineno = frame.lineno

  timestamp = datetime.now()
  time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
  msg_parts = [
    time_str,
    f'{filename}:{lineno}',
    ' '.join(map(str, msg))
  ]
  line = ' - '.join(filter(None, msg_parts))

  print(line)
