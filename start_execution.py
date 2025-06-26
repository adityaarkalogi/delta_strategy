import logging
import logging.config
from datetime import datetime
import os
import engine


# Ensure the log directory exists
LOG_DIR = "./logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Define log file path
log_file_path = os.path.join(LOG_DIR, f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


class MyFilter(logging.Filter):
    def __init__(self, filter_msg):
        super(MyFilter, self).__init__()

        self.filter_msg = filter_msg

    def filter(self, record):
        """
        :param record: LogRecord Object
        :return True to accept record, False to drop record
        """

        # if record.levelname == 'INFO':
        #     return False
        # else:
        #     record.msg += self.filter_msg
        return True

dict_config = {
    'version': 1,
    'disable_existing_loggers': False, # default True
    'filters': {
        'my_filter': {
            '()': MyFilter,
            'filter_msg': 'show how to use filter'
        }
    },
    'formatters': {
        'user_info': {
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)-8s - %(asctime)s - %(message)s'
        },
        'brief': {
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)-8s - %(name)s - %(message)s'
        },
        'single-line': {
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)-8s - %(asctime)s - %(name)s - %(module)s - %(funcName)s - line no. %(lineno)d: %(message)s'
        },
        'multi-process': {
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)-8s - [%(process)d] - %(name)s - %(module)s:%(funcName)s - %(lineno)d: %(message)s'
        },
        'multi-thread': {
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)-8s - %(threadName)s - %(name)s - %(module)s:%(funcName)s - %(lineno)d: %(message)s'
        },
        'verbose': {
            'format': '%(asctime)s - %(levelname)-8s - [%(process)d] - %(threadName)s - %(name)s - %(module)s:%(funcName)s - %(lineno)d'
                    ': %(message)s'
        },
        'multiline': {
            'format': 'Level: %(levelname)s\nTime: %(asctime)s\nProcess: %(process)d\nThread: %(threadName)s\nLogger'
                    ': %(name)s\nPath: %(module)s:%(lineno)d\nFunction :%(funcName)s\nMessage: %(message)s\n'
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'user_info',
            'filters': ['my_filter'],
            # 'stream': 'ext://sys.stdout'
        },
        'file_handler': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': log_file_path,
        },
        'null_handler': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        'root': {  # this is root logger
            'level': 'DEBUG',
            'handlers': ['console', 'file_handler'],
        },
        'parent': {
            'level': 'DEBUG',
            'handlers': ['console', 'file_handler'],
        },
        'parent.child': {  # This is child logger of `parent` handler, propagate will up to `parent` handler
            'level': 'DEBUG',
            'handlers': ['console', 'file_handler'],
        },
    }
}


logging.config.dictConfig(dict_config)
logger = logging.getLogger("root")


if __name__ == "__main__":
    try:
        engine.setup()
    except:
        logger.critical("Error in setup", exc_info=True)
        exit(1)

    try:
        logger.info(f"Runninggg...")
        engine.run()
    except:
        logger.critical("Runtime Error", exc_info=True)