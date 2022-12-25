import sqlite3
from datetime import datetime
from loguru import logger
from datetime_utils import to_unix


def get_db() -> sqlite3.Connection:
    SCHEMA = """
    create table if not exists activities (
        id integer primary key autoincrement,
        name text not null unique
    );
    
    create table if not exists users_cache (
        user_id integer primary key,
        nickname text not null
    );
    
    create table if not exists presence_journal (
        user_id integer not null,
        start_time integer not null,  -- In unix timestamp
        end_time integer not null,
        activity_name_id integer not null,
        primary key (user_id, start_time),
        foreign key (activity_name_id) references activities(id)
    );"""

    db = sqlite3.connect('presence-tracker.sqlite')
    db.executescript(SCHEMA)
    return db


class PresenceTracker:
    def __init__(self, db: sqlite3.Connection = get_db()):
        self.db = db

    def log_activity(self, user_id: int, activity_name: str, start_time: datetime, end_time: datetime | None = None):
        """Create record or update uncommited end_time"""

        # end_time behaves like "last seen with this activity"

        logger.info(f'Logging {user_id=}, {activity_name=}, {start_time.isoformat()=}, {end_time=}')

        activity_id = self.get_activity_id(activity_name)
        _end_time = self.to_unix_default(end_time)  # Defaulted end_time

        unix_start_time = to_unix(start_time)

        if unix_start_time > _end_time:
            logger.warning(f'Got {unix_start_time=} > {_end_time}, {_end_time - unix_start_time=}, {user_id=}, {activity_name=}')


        with self.db:
            self.db.execute(
                    """insert into presence_journal (user_id, start_time, activity_name_id, end_time) 
                        values (:user_id, :start_time, :activity_name_id, :end_time) 
                    on conflict do update set end_time = :end_time;""",
                {
                    'user_id': user_id,
                    'start_time': to_unix(start_time),
                    'activity_name_id': activity_id,
                    'end_time': _end_time
                }
            )

    def get_activity_id(self, activity_name: str) -> int:
        """Get id for given activity, for insert to another table, for example"""

        # Try to find first, insert after
        params = (activity_name,)
        query = self.db.execute('select id from activities where name = ?;', params).fetchone()
        if query is not None:
            logger.trace(f'Found record for {activity_name!r} id={query}')
            return query[0]

        with self.db:
            query = self.db.execute('insert into activities (name) values (?) returning id;', params).fetchone()

        logger.debug(f'Inserted record for {activity_name!r} {query}')
        return query[0]

    def saturate_users_cache(self, user_id: int, user_name: str):
        """Ensure given user is in cache or add a user to cache"""

        logger.trace(f'Adding {user_name!r} to cache')
        with self.db:
            self.db.execute(
                'insert or ignore into users_cache (user_id, nickname) VALUES (?, ?);',
                (user_id, user_name)
            )

    def user_breakdown(self, user_id: int) -> dict[str, int]:
        """Return dict with activities names as keys and spent time in hours as values"""

        res = self.db.execute(
            'select a.name, round(sum(end_time - start_time) / 3600.0, 1) as total '
            'from presence_journal '
            'left join activities a on a.id = presence_journal.activity_name_id '
            'where user_id = ? '
            'group by activity_name_id '
            'order by total desc;',
            (user_id,)
        ).fetchall()

        return {row[0]: row[1] for row in res}

    def top_users(self, last_days: int | None) -> dict[int, tuple[str | None, int]]:
        """Returns keys - ids, values - tuple(nickname?, hours spent)"""  # TODO: implement last_daysa

        res = self.db.execute(
            """select uc.user_id, uc.nickname, round(sum(end_time - presence_journal.start_time) / 3600.0, 1) as total
            from presence_journal left join users_cache uc on presence_journal.user_id = uc.user_id
            group by uc.user_id
            order by total desc
            limit 50;""").fetchall()

        return {row[0]: row[1:3] for row in res}

    def top_games(self) -> dict[str, int]:
        """Returns keys - names, values - spent hours"""
        res = self.db.execute(
            """select a.name, round(sum(end_time - presence_journal.start_time) / 3600.0) as total
            from presence_journal left join activities a on a.id = presence_journal.activity_name_id
            group by activity_name_id
            order by total desc
            limit 50;""").fetchall()

        return {row[0]: row[1] for row in res}

    @staticmethod
    def default_end_time(end_time: datetime | None) -> datetime:
        return datetime.now() if end_time is None else end_time

    def to_unix_default(self, end_time: datetime | None) -> int:
        return to_unix(self.default_end_time(end_time))
