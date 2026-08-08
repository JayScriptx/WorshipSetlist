"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "songs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist", sa.String(length=255), nullable=True),
        sa.Column("original_key", sa.String(length=10), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("time_signature", sa.String(length=10), nullable=False, server_default="4/4"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_songs_title", "songs", ["title"])
    op.create_index("ix_songs_artist", "songs", ["artist"])

    op.create_table(
        "song_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("song_id", sa.Integer(), sa.ForeignKey("songs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_name", sa.String(length=50), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_song_sections_song_id", "song_sections", ["song_id"])

    op.create_table(
        "setlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_setlists_name", "setlists", ["name"])
    op.create_index("ix_setlists_date", "setlists", ["date"])

    op.create_table(
        "setlist_songs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setlist_id", sa.Integer(), sa.ForeignKey("setlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("song_id", sa.Integer(), sa.ForeignKey("songs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("song_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key_override", sa.String(length=10), nullable=True),
        sa.Column("bpm_override", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("song_title_snapshot", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("song_artist_snapshot", sa.String(length=255), nullable=True),
        sa.Column("has_custom_arrangement", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_setlist_songs_setlist_id", "setlist_songs", ["setlist_id"])
    op.create_index("ix_setlist_songs_song_id", "setlist_songs", ["song_id"])

    op.create_table(
        "setlist_song_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "setlist_song_id",
            sa.Integer(),
            sa.ForeignKey("setlist_songs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_name", sa.String(length=50), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_setlist_song_sections_setlist_song_id", "setlist_song_sections", ["setlist_song_id"])


def downgrade() -> None:
    op.drop_table("setlist_song_sections")
    op.drop_table("setlist_songs")
    op.drop_table("setlists")
    op.drop_table("song_sections")
    op.drop_table("songs")
    op.drop_table("users")
