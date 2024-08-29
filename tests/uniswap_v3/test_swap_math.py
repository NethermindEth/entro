from nethermind.entro.uniswap_v3.math import UniswapV3Math

from ..utils import expand_to_decimals
from .utils import encode_sqrt_price

UniswapV3Math.initialize_exact_math()


class TestComputeSwapStep:
    def test_exact_amount_in_gets_capped_at_price_target_one_for_zero(self, initialize_empty_pool):
        price = encode_sqrt_price(1, 1)
        price_target = encode_sqrt_price(101, 100)
        liquidity = expand_to_decimals(2, 18)
        amount = expand_to_decimals(1, 18)
        swap_step = UniswapV3Math.compute_swap_step(
            price,
            price_target,
            liquidity,
            amount,
            600,
        )

        assert swap_step.amount_in == 9975124224178055
        assert swap_step.fee_amount == 5988667735148
        assert swap_step.amount_out == 9925619580021728
        assert swap_step.amount_in + swap_step.fee_amount < amount

        price_after_whole_input_amount = UniswapV3Math.get_next_sqrt_price_from_input(
            price,
            liquidity,
            amount,
            False,
        )
        assert swap_step.sqrt_price_next == price_target
        assert swap_step.sqrt_price_next < price_after_whole_input_amount

    def test_exact_amount_out_gets_capped_at_price_target_one_for_zero(self, initialize_empty_pool):
        price = encode_sqrt_price(1, 1)
        price_target = encode_sqrt_price(101, 100)
        liquidity = expand_to_decimals(2, 18)
        amount = expand_to_decimals(1, 18) * -1
        swap_step = UniswapV3Math.compute_swap_step(
            price,
            price_target,
            liquidity,
            amount,
            600,
        )

        assert swap_step.amount_in == 9975124224178055
        assert swap_step.fee_amount == 5988667735148
        assert swap_step.amount_out == 9925619580021728
        assert swap_step.amount_out < amount * -1

        price_after_whole_output_amount = UniswapV3Math.get_next_sqrt_price_from_input(
            price,
            liquidity,
            amount * -1,
            False,
        )
        assert swap_step.sqrt_price_next == price_target
        assert swap_step.sqrt_price_next < price_after_whole_output_amount

    def test_exact_amount_in_fully_spent_one_for_zero(self, initialize_empty_pool):
        price = encode_sqrt_price(1, 1)
        price_target = encode_sqrt_price(1000, 100)
        liquidity = expand_to_decimals(2, 18)
        amount = expand_to_decimals(1, 18)

        swap_step = UniswapV3Math.compute_swap_step(
            price,
            price_target,
            liquidity,
            amount,
            600,
        )

        assert swap_step.amount_in == 999400000000000000
        assert swap_step.fee_amount == 600000000000000
        assert swap_step.amount_out == 666399946655997866
        assert swap_step.amount_in + swap_step.fee_amount == amount

        price_after_whole_input_amount_no_fee = UniswapV3Math.get_next_sqrt_price_from_input(
            price,
            liquidity,
            amount - swap_step.fee_amount,
            False,
        )

        assert swap_step.sqrt_price_next < price_target
        assert swap_step.sqrt_price_next == price_after_whole_input_amount_no_fee

    def test_exact_amount_out_fully_recieved_one_for_zero(self, initialize_empty_pool):
        price = encode_sqrt_price(1, 1)
        price_target = encode_sqrt_price(10000, 100)
        liquidity = expand_to_decimals(2, 18)
        amount = expand_to_decimals(1, 18) * -1

        swap_step = UniswapV3Math.compute_swap_step(
            price,
            price_target,
            liquidity,
            amount,
            600,
        )

        assert swap_step.amount_in == 2000000000000000000
        assert swap_step.fee_amount == 1200720432259356
        assert swap_step.amount_out == amount * -1

        price_after_whole_output_amount = UniswapV3Math.get_next_sqrt_price_from_output(
            price,
            liquidity,
            amount * -1,
            False,
        )

        assert swap_step.sqrt_price_next < price_target
        assert swap_step.sqrt_price_next == price_after_whole_output_amount

    def test_amount_out_capped_at_desired_amount_out(self, initialize_empty_pool):
        swap_step = UniswapV3Math.compute_swap_step(
            417332158212080721273783715441582,
            1452870262520218020823638996,
            159344665391607089467575320103,
            -1,
            1,
        )

        assert swap_step.amount_in == 1
        assert swap_step.fee_amount == 1
        assert swap_step.amount_out == 1
        assert swap_step.sqrt_price_next == 417332158212080721273783715441581

    def test_target_price_of_1_uses_partial_input_amount(self, initialize_empty_pool):
        pool = initialize_empty_pool()
        swap_step = UniswapV3Math.compute_swap_step(
            2,
            1,
            1,
            3915081100057732413702495386755767,
            1,
        )

        assert swap_step.amount_in == 39614081257132168796771975168
        assert swap_step.fee_amount == 39614120871253040049813
        assert swap_step.amount_in + swap_step.fee_amount <= 3915081100057732413702495386755767
        assert swap_step.amount_out == 0
        assert swap_step.sqrt_price_next == 1

    def test_entire_input_amount_taken_as_fee(self, initialize_empty_pool):
        swap_step = UniswapV3Math.compute_swap_step(
            2413,
            79887613182836312,
            1985041575832132834610021537970,
            10,
            1872,
        )

        assert swap_step.amount_in == 0
        assert swap_step.fee_amount == 10
        assert swap_step.amount_out == 0
        assert swap_step.sqrt_price_next == 2413

    def test_handles_intermediate_insufficient_liqudity_exact_output_zero_for_one(self, initialize_empty_pool):
        sqrt_price = 20282409603651670423947251286016
        sqrt_price_target = int((sqrt_price * 11) / 10)
        swap_step = UniswapV3Math.compute_swap_step(
            sqrt_price,
            sqrt_price_target,
            1024,
            -4,
            3000,
        )

        assert swap_step.amount_out == 0
        assert swap_step.sqrt_price_next == sqrt_price_target
        assert swap_step.amount_in == 26215
        assert swap_step.fee_amount == 79

    def test_handes_intermediate_insufficient_liquidity_exact_output_one_for_zero(self, initialize_empty_pool):
        sqrt_price = 20282409603651670423947251286016
        sqrt_price_target = int((sqrt_price * 9) / 10)
        swap_step = UniswapV3Math.compute_swap_step(
            sqrt_price,
            sqrt_price_target,
            1024,
            -263000,
            3000,
        )

        assert swap_step.amount_out == 26214
        assert swap_step.sqrt_price_next == sqrt_price_target
        assert swap_step.amount_in == 1
        assert swap_step.fee_amount == 1
