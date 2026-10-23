"""Plain step plans for helper jobs, so the window and the website say what is running now and what comes next.

The helper does not choose work. It runs whatever Neptune queued and describes it with these plans.
"""

# (title, [(step name, message prefixes that mean this step is running)])
PLANS = {
    'prepare': ('Prepare frames for Robot labels', [
        ('Download the match video', ('Downloading',)),
        ('Find bumpers in each frame', ('Finding bumpers',)),
        ('Send the boxes to Robot labels', ('Prepared',)),
    ]),
    'train': ('Train the robot detector', [
        ('Download robot labels', ('Downloading robot labels',)),
        ('Prepare training frames', ('Preparing', 'Downloading')),
        ('Train', ('Training robot detector',)),
        ('Compare with the detector in use', ('Comparing',)),
        ('Share it if better', ('Sharing', 'Adopted', 'Kept')),
    ]),
    'train_field': ('Train the field detector', [
        ('Download scoring areas', ('Downloading scoring areas',)),
        ('Prepare field frames', ('Preparing field frames', 'Downloading')),
        ('Train', ('Training field detector',)),
        ('Compare with the detector in use', ('Comparing',)),
        ('Share it if better', ('Sharing', 'Adopted', 'Kept')),
    ]),
    'actions': ('Train action models & scoring', [
        ('Collect tags and imports', ('Syncing', 'Preparing training', 'Checking saved')),
        ('Prepare each match: video, numbers, robot tracking', ('[', 'Verifying', 'Refreshing', 'Tracking', 'Extracting', 'Preparing', 'Reusing', 'Rechecked')),
        ('Fit action and scoring models', ('Fitting',)),
        ('Check on held-out matches and save', ('Evaluating', 'Recovering', 'Finished')),
    ]),
}


class Steps:
    """Turns raw progress messages into 'step N of M / Now / Next'. Steps only move forward."""

    def __init__(self, kind):
        self.title, self.steps = PLANS[kind]
        self.at = 0

    def describe(self, message):
        message = str(message)
        for i in range(self.at, len(self.steps)):
            if message.startswith(self.steps[i][1]):
                self.at = i
                break
        name = self.steps[self.at][0]
        upcoming = [s[0] for s in self.steps[self.at+1:]]
        lines = ['%s · step %d of %d: %s' % (self.title, self.at+1, len(self.steps), name), 'Now: '+message]
        lines.append('Next: '+(' → '.join(upcoming) if upcoming else 'done'))
        return '\n'.join(lines)
