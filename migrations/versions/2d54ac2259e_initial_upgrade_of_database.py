"""Initial upgrade of database.

Revision ID: 2d54ac2259e
Revises: None
Create Date: 2015-11-17 14:07:59.563838

"""

# revision identifiers, used by Alembic.
revision = '2d54ac2259e'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('feeds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('author_secret', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('db_moment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(length=2400), nullable=True),
    sa.Column('feed_id', sa.Integer(), nullable=True),
    sa.Column('date_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['feed_id'], ['feeds.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('db_moment')
    op.drop_table('feeds')
    ### end Alembic commands ###