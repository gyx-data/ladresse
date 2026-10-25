"""File d'événements temporisés (alimentée par le temps de jeu, donc suspendue en pause)."""
import heapq
import itertools


class TimerQueue:
    def __init__(self):
        self.t = 0.0
        self._h = []
        self._c = itertools.count()

    def after(self, delay, fn, *args, **kw):
        """Exécute fn(*args, **kw) dans `delay` secondes de temps de jeu. Retourne un identifiant."""
        tid = next(self._c)
        heapq.heappush(self._h, (self.t + delay, tid, fn, args, kw))
        return tid

    def at(self, when, fn, *args, **kw):
        tid = next(self._c)
        heapq.heappush(self._h, (when, tid, fn, args, kw))
        return tid

    def cancel(self, tid):
        self._h = [e for e in self._h if e[1] != tid]
        heapq.heapify(self._h)

    def clear(self):
        self._h = []

    def update(self, dt):
        self.t += dt
        while self._h and self._h[0][0] <= self.t:
            _, _, fn, args, kw = heapq.heappop(self._h)
            fn(*args, **kw)

    def pending(self):
        return len(self._h)
