import logging
import uuid
from typing import Any, Literal, Sequence

from nethermind.entro.database.models.internal import BackfilledRange
from nethermind.entro.exceptions import BackfillError

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("ranges")


class BackfillRangePlan:
    """Describes the backfill plan for a given block range"""

    backfill_ranges: list[tuple[int, int]]
    backfill_mode: Literal["new", "extend", "join", "empty"]
    conflicts: list[BackfilledRange]

    remove_backfills: list[BackfilledRange]
    add_backfill: BackfilledRange | None = None

    def __init__(
        self,
        from_block: int,
        to_block: int,
        conflicts: list[BackfilledRange],
    ):
        self.conflicts = conflicts
        self.remove_backfills = []
        self.add_backfill = None

        if len(conflicts) == 0:
            self.backfill_ranges = [(from_block, to_block)]
            self.backfill_mode = "new"
        elif len(conflicts) == 1:
            self._compute_extend(from_block=from_block, to_block=to_block)
        elif len(conflicts) > 1:
            self._compute_join(from_block=from_block, to_block=to_block)
        else:
            raise BackfillError("Invalid Backfill Range Plan")

    def _compute_extend(self, from_block: int, to_block: int):
        ranges = []
        backfill = self.conflicts[0]
        if from_block < backfill.start_block:
            ranges.append((from_block, backfill.start_block))
        if to_block > backfill.end_block:
            ranges.append((backfill.end_block, to_block))

        self.backfill_ranges = ranges
        self.backfill_mode = "extend" if ranges else "empty"

    def _compute_join(
        self,
        from_block: int,
        to_block: int,
    ):
        ranges: list[tuple[int, int]] = []
        search_block = from_block

        for index, conflict_bfill in enumerate(self.conflicts):
            # -- Handle Start Block Conditions --
            if search_block < conflict_bfill.start_block:
                ranges.append((search_block, conflict_bfill.start_block))

            # -- Handle End Block Conditions --
            if conflict_bfill.end_block >= to_block:
                # To block inside current backfill (This is also final iter)
                break
            if index == len(self.conflicts) - 1:
                # Reached end of conflicts, but to_block is after last end_block
                ranges.append((conflict_bfill.end_block, to_block))
            else:
                search_block = conflict_bfill.end_block

        # Ranges should never be empty
        self.backfill_ranges = ranges
        self.backfill_mode = "join"

    @classmethod
    def compute_db_backfills(
        cls,
        from_block: int,
        to_block: int,
        conflicting_backfills: Sequence[BackfilledRange],
    ) -> "BackfillRangePlan":
        """
        Generates a backfill plan for a given block range and conflicting backfills.

        :param from_block:
        :param to_block:
        :param conflicting_backfills:
        :return:
        """

        in_range_backfills = [
            b for b in conflicting_backfills if b.end_block >= from_block and b.start_block <= to_block
        ]

        logger.info(
            f"Computing Backfill Ranges for Blocks ({from_block} - {to_block}) with Conflicting Backfills: "
            f"{[(b.start_block, b.end_block) for b in in_range_backfills]}"
        )

        return BackfillRangePlan(
            from_block=from_block,
            to_block=to_block,
            conflicts=sorted(in_range_backfills, key=lambda x: x.start_block),
        )

    def _process_extend(self, finished_range: tuple[int, int]):
        print(f"Processing Extend: {finished_range}")
        print(f"Add Backfill: {self.add_backfill}")
        if self.add_backfill is None:
            raise BackfillError("Cannot Extend Non-existent Add Backfill")

        if finished_range[0] == self.add_backfill.end_block:
            # First backfill range starts after first conflict
            self.add_backfill.end_block = finished_range[1]
        elif finished_range[1] == self.add_backfill.start_block:
            # First backfill range starts before first conflict
            self.add_backfill.start_block = finished_range[0]
        else:
            raise BackfillError("Cannot Join Backfill to Non-Adjacent Range")

    def mark_finalized(self, range_index: int, range_kwargs: dict[str, Any]):
        """
        Marks a given range as finalized, updating remove and add backfills accordingly

        :param range_index: 0-indexed position of backfill range completed
        :return:
        """
        r_len = len(self.backfill_ranges)
        if range_index >= r_len:
            raise BackfillError(
                f"Backfill only contains {r_len} range{'s' if r_len > 1 else ''}... Cannot finalize Range "
                f"#{range_index + 1}"
            )

        finalized_range = self.backfill_ranges[range_index]

        match self.backfill_mode:
            case "new":
                self.add_backfill = BackfilledRange(
                    backfill_id=uuid.uuid4().hex,
                    start_block=finalized_range[0],
                    end_block=finalized_range[1],
                    **range_kwargs,
                )

            case "extend":
                if not self.add_backfill:
                    self.add_backfill = self.conflicts.pop(0)
                self._process_extend(finalized_range)

            case "join":
                if self.add_backfill is None:  # First Iteration
                    self.add_backfill = self.conflicts.pop(0)
                    self._process_extend(finalized_range)

                try:
                    next_bfill = self.conflicts[0]
                except IndexError:
                    self.add_backfill.end_block = finalized_range[1]
                    return

                if next_bfill.start_block == finalized_range[1]:
                    self.add_backfill.end_block = next_bfill.end_block
                    self.remove_backfills.append(self.conflicts.pop(0))

    def mark_failed(self, range_index: int, final_block: int, range_kwargs: dict[str, Any]):
        """
        Marks a backfill range as failed, saving current state to database.

        :param range_index:  0-indexed position of backfill range that failure occurred in
        :param final_block:  Block number that failure occurred at
        :return:
        """
        if range_index >= len(self.backfill_ranges):
            raise BackfillError("Backfill Range for Failiure Does Not Exist")
        fail_range = self.backfill_ranges[range_index]
        if not fail_range[0] <= final_block < fail_range[1]:
            raise BackfillError(f"Failiure Occured at block {final_block} Outside of Expected Range {fail_range}")
        if fail_range[0] == final_block:
            # No blocks in range were backfilled
            return

        if self.add_backfill:
            self.add_backfill.end_block = final_block
        else:
            match self.backfill_mode:
                case "new":
                    self.add_backfill = BackfilledRange(
                        backfill_id=uuid.uuid4().hex,
                        start_block=fail_range[0],
                        end_block=final_block,
                        **range_kwargs,
                    )
                case "extend":
                    if fail_range[0] == self.conflicts[0].end_block:
                        self.add_backfill = self.conflicts[0]
                        self.add_backfill.end_block = final_block
                    else:
                        self.add_backfill = BackfilledRange(
                            backfill_id=uuid.uuid4().hex,
                            start_block=fail_range[0],
                            end_block=final_block,
                            **range_kwargs,
                        )
                case "join":
                    if self.add_backfill:
                        self.add_backfill.end_block = final_block
                    else:
                        self.add_backfill = BackfilledRange(
                            backfill_id=uuid.uuid4().hex,
                            start_block=fail_range[0],
                            end_block=final_block,
                            **range_kwargs,
                        )
