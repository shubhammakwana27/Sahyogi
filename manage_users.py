"""Local operator setup and password recovery. Never puts passwords in arguments."""
import argparse
import getpass
import os
from pathlib import Path
from access_control import Accounts, PASSWORD_RULE
from store import Store

ROOT=Path(__file__).resolve().parent


def password_twice():
    first=getpass.getpass(f'Choose a password or passphrase ({PASSWORD_RULE}): ')
    if first!=getpass.getpass('Repeat the password: '):raise ValueError('The passwords do not match.')
    return first


def bootstrap_if_needed(store):
    accounts=Accounts(store)
    if not accounts.has_users():
        print('First start: create the initial coordinator account. There is no default password.')
        accounts.create_user(input('Coordinator username: '),input('Coordinator display name: '),'coordinator',password_twice(),bootstrap=True)
        print('Coordinator created. Existing cases were assigned to this account. Sign in in your browser.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['setup','reset-password'])
    parser.add_argument('--database',default=os.getenv('SAHYOGI_DB',str(ROOT/'data'/'sahyogi.db')))
    args=parser.parse_args();store=Store(args.database)
    try:
        if args.action=='setup':bootstrap_if_needed(store)
        else:
            name=input('Username to reset: ');new=password_twice();Accounts(store).reset_local(name,new)
            print('Temporary password set. Previous sessions were signed out. Tell the account holder privately.')
        return 0
    except (ValueError,KeyboardInterrupt,EOFError) as error:
        print(str(error) or 'Setup stopped.');return 1


if __name__=='__main__':raise SystemExit(main())
