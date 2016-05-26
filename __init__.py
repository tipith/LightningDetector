###
# Copyright (c) 2016, Timo Pihlstrom
# All rights reserved.
#
#
###

"""
LightningDetector: Detects lightning strikes based on Finnish Meteorological Institute's open data
"""

import supybot
import supybot.world as world

# Use this for the version of this plugin.  You may wish to put a CVS keyword
# in here if you're keeping the plugin in CVS or some similar system.
__version__ = "0.1"

# XXX Replace this with an appropriate author or supybot.Author instance.
__author__ = supybot.Author('Timo Pihlstrom', 'tipi^')

# This is a dictionary mapping supybot.Author instances to lists of
# contributions.
__contributors__ = {}

# This is a url where the most recent plugin package can be downloaded.
__url__ = ''

from . import config
from . import plugin
from . import fmiapi
from . import userconf
from imp import reload
# In case we're being reloaded.
reload(config)
reload(plugin)
reload(fmiapi)
reload(userconf)
# Add more reloads here if you add third-party modules and want them to be
# reloaded when this plugin is reloaded.  Don't forget to import them as well!

if world.testing:
    from . import test

Class = plugin.Class
configure = config.configure


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
