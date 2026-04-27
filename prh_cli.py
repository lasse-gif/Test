#!/usr/bin/env python3
"""
PRH Tilinpäätöshaku – komentorivityökalu

Käyttö:
  python prh_cli.py hae <yrityksen nimi>
  python prh_cli.py tiedot <Y-tunnus>
  python prh_cli.py jaksot <Y-tunnus>
  python prh_cli.py tilinpaatos <Y-tunnus> <YYYY-MM-DD>
  python prh_cli.py interaktiivinen

Esimerkit:
  python prh_cli.py hae "Nokia"
  python prh_cli.py jaksot 0112038-9
  python prh_cli.py tilinpaatos 0112038-9 2023-12-31
"""

import sys
from prh_client import (
    PRHClientError,
    get_company,
    get_financial_periods,
    get_financial_statement,
    print_company,
    print_periods,
    print_statement,
    search_companies,
)


def cmd_hae(args: list[str]) -> int:
    if not args:
        print("Virhe: anna hakusana. Esim: python prh_cli.py hae Nokia")
        return 1
    name = " ".join(args)
    print(f"\nHaetaan yrityksiä nimellä: {name!r} ...")
    try:
        companies = search_companies(name=name)
    except PRHClientError as e:
        print(f"Virhe: {e}")
        return 1

    if not companies:
        print("Ei hakutuloksia.")
        return 0

    print(f"\n  Löytyi {len(companies)} yritystä:\n")
    print(f"  {'Y-tunnus':<14} {'Yhtiömuoto':<8} {'Nimi'}")
    print(f"  {'─'*60}")
    for c in companies:
        print(f"  {c.business_id:<14} {c.company_form:<8} {c.name}")
    print()
    return 0


def cmd_tiedot(args: list[str]) -> int:
    if not args:
        print("Virhe: anna Y-tunnus. Esim: python prh_cli.py tiedot 0112038-9")
        return 1
    business_id = args[0]
    print(f"\nHaetaan yritystiedot: {business_id} ...")
    try:
        company = get_company(business_id)
    except PRHClientError as e:
        print(f"Virhe: {e}")
        return 1

    if not company:
        print("Yritystä ei löydy.")
        return 0

    print_company(company)
    print()
    return 0


def cmd_jaksot(args: list[str]) -> int:
    if not args:
        print("Virhe: anna Y-tunnus. Esim: python prh_cli.py jaksot 0112038-9")
        return 1
    business_id = args[0]
    print(f"\nHaetaan tilinpäätösjaksot: {business_id} ...")

    try:
        company = get_company(business_id)
        if company:
            print_company(company)
        periods = get_financial_periods(business_id)
    except PRHClientError as e:
        print(f"Virhe: {e}")
        return 1

    print(f"\n  Saatavilla olevat tilinpäätökset (IXBRL-muoto):")
    print_periods(periods)

    if periods:
        print(f"\n  Hae tilinpäätös komennolla:")
        p = periods[0]
        print(f"  python prh_cli.py tilinpaatos {business_id} {p.period_end}")
    print()
    return 0


def cmd_tilinpaatos(args: list[str]) -> int:
    if len(args) < 2:
        print("Virhe: anna Y-tunnus ja päätöspäivä.")
        print("Esim: python prh_cli.py tilinpaatos 0112038-9 2023-12-31")
        return 1
    business_id, financial_date = args[0], args[1]
    print(f"\nHaetaan tilinpäätös: {business_id} / {financial_date} ...")
    try:
        statement = get_financial_statement(business_id, financial_date)
    except PRHClientError as e:
        print(f"Virhe: {e}")
        return 1

    if not statement:
        print("Tilinpäätöstä ei löydy.")
        return 0

    print_statement(statement, business_id, financial_date)
    return 0


def cmd_interaktiivinen() -> int:
    print("\n" + "═" * 52)
    print("  PRH Tilinpäätöshaku – interaktiivinen tila")
    print("═" * 52)
    print("  Komennot: hae / tiedot / jaksot / tilinpaatos / lopeta\n")

    dispatch = {
        "hae": cmd_hae,
        "tiedot": cmd_tiedot,
        "jaksot": cmd_jaksot,
        "tilinpaatos": cmd_tilinpaatos,
    }

    while True:
        try:
            line = input("prh> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSuljetaan.")
            break
        if not line:
            continue
        parts = line.split()
        cmd, rest = parts[0].lower(), parts[1:]
        if cmd in ("lopeta", "quit", "exit", "q"):
            print("Suljetaan.")
            break
        if cmd in dispatch:
            dispatch[cmd](rest)
        else:
            print(f"  Tuntematon komento: {cmd!r}")
            print(f"  Komennot: {', '.join(dispatch.keys())}, lopeta")

    return 0


COMMANDS = {
    "hae": cmd_hae,
    "tiedot": cmd_tiedot,
    "jaksot": cmd_jaksot,
    "tilinpaatos": cmd_tilinpaatos,
}


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd = args[0].lower()

    if cmd == "interaktiivinen":
        return cmd_interaktiivinen()

    if cmd not in COMMANDS:
        print(f"Tuntematon komento: {cmd!r}")
        print(f"Komennot: {', '.join(COMMANDS)} interaktiivinen")
        print("Lisätietoja: python prh_cli.py --help")
        return 1

    return COMMANDS[cmd](args[1:])


if __name__ == "__main__":
    sys.exit(main())
