# coding=utf-8
#
# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis-python
#
# Most of this work is copyright (C) 2013-2015 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# END HEADER

from __future__ import division, print_function, absolute_import

from contextlib import contextmanager

from hypothesis.errors import InvalidArgument
from hypothesis.internal.reflection import get_pretty_function_description
from hypothesis.searchstrategy.wrappers import WrapperStrategy
from hypothesis.searchstrategy.strategies import OneOfStrategy, \
    SearchStrategy


class LimitReached(BaseException):
    pass


class LimitedStrategy(WrapperStrategy):

    def __init__(self, strategy):
        super(LimitedStrategy, self).__init__(strategy)
        self.marker = 0
        self.currently_capped = False

    def do_draw(self, data):
        assert self.currently_capped
        if self.marker <= 0:
            raise LimitReached()
        self.marker -= 1
        return super(LimitedStrategy, self).do_draw(data)

    @contextmanager
    def capped(self, max_templates):
        assert not self.currently_capped
        try:
            self.currently_capped = True
            self.marker = max_templates
            yield
        finally:
            self.currently_capped = False


class RecursiveStrategy(SearchStrategy):

    def __init__(self, base, extend, max_leaves):
        self.max_leaves = max_leaves
        self.base = LimitedStrategy(base)
        self.extend = extend

        strategies = [self.base, self.extend(self.base)]
        while 2 ** len(strategies) <= max_leaves:
            strategies.append(
                extend(OneOfStrategy(tuple(strategies), bias=0.8)))
        self.strategy = OneOfStrategy(strategies)

    def __repr__(self):
        if not hasattr(self, '_cached_repr'):
            self._cached_repr = u'recursive(%r, %s, max_leaves=%d)' % (
                self.base.wrapped_strategy, get_pretty_function_description(
                    self.extend), self.max_leaves
            )
        return self._cached_repr

    def validate(self):
        if not isinstance(self.base, SearchStrategy):
            raise InvalidArgument(
                'Expected base to be SearchStrategy but got %r' % (self.base,)
            )
        extended = self.extend(self.base)
        if not isinstance(extended, SearchStrategy):
            raise InvalidArgument(
                'Expected extend(%r) to be a SearchStrategy but got %r' % (
                    self.base, extended
                ))
        self.base.validate()
        self.extend(self.base).validate()

    def do_draw(self, data):
        count = 0
        while True:
            try:
                with self.base.capped(self.max_leaves):
                    return data.draw(self.strategy)
            except LimitReached:
                if count == 0:
                    data.note_event((
                        'Draw for %r exceeded max_leaves '
                        'and had to be retried') % (self,))
                count += 1
