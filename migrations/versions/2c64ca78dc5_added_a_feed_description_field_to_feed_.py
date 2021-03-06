"""Added a feed description field to feed entries.

Revision ID: 2c64ca78dc5
Revises: 18bd14dd0a8
Create Date: 2015-11-25 13:25:10.119784

"""

# revision identifiers, used by Alembic.
revision = '2c64ca78dc5'
down_revision = '18bd14dd0a8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    default_desc = "Placeholder description."
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feeds', sa.Column('feed_desc',
                                     sa.String(length=2400),
                                     nullable=True,
                                     default=default_desc))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('feeds', 'feed_desc')
    ### end Alembic commands ###
