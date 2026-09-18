# 전략 아이디어를 입력받아 비용 게이트 통과 여부를 출력하는 명령줄 도구 (M0, D-013)

import argparse
import sys

from costgate.model import CostModel, evaluate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="costgate",
        description="전략 아이디어가 거래 마찰을 넘을 수 있는지 코딩 전에 판정한다 (D-013)",
    )
    parser.add_argument(
        "--commission-buy", type=float, required=True, help="매수 수수료율 (%%)"
    )
    parser.add_argument(
        "--commission-sell", type=float, required=True, help="매도 수수료율 (%%)"
    )
    parser.add_argument(
        "--slippage", type=float, required=True, help="왕복 슬리피지 (%%)"
    )
    parser.add_argument("--stop-loss", type=float, required=True, help="손절폭 (%%)")
    parser.add_argument(
        "--reward-risk", type=float, required=True, help="목표 손익비 (2면 2:1)"
    )
    parser.add_argument(
        "--round-trips", type=float, required=True, help="일 왕복 횟수"
    )
    parser.add_argument(
        "--win-rate", type=float, required=True, help="이 전략이 낼 것으로 가정하는 승률 (%%)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cost = CostModel(
        commission_buy_pct=args.commission_buy,
        commission_sell_pct=args.commission_sell,
        slippage_round_trip_pct=args.slippage,
    )
    result = evaluate(
        cost=cost,
        stop_loss_pct=args.stop_loss,
        reward_risk=args.reward_risk,
        round_trips_per_day=args.round_trips,
        assumed_win_rate_pct=args.win_rate,
    )

    print(f"왕복 마찰        f = {result.friction_pct:.3f}%")
    print(f"본전 승률        p = {result.breakeven_win_rate_pct:.1f}%")
    print(f"가정 승률            {result.assumed_win_rate_pct:.1f}%")
    print(f"여유                 {result.margin_pp:+.1f}%p")
    print(
        f"월 마찰 소모         {result.monthly_friction_pct:.1f}% "
        f"(왕복 {args.round_trips}회/일, 매회 전량 투입 가정)"
    )
    print()

    if result.passed:
        print("판정: 통과")
        print("여유가 실제로 충분한지는 관찰 데이터로 확인해야 한다. 통과가 수익 보장은 아니다.")
    else:
        print("판정: 탈락")
        for violation in result.violations:
            print(f"  - {violation}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
