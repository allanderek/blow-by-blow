earliest_first = false
feed_successfully_updated = 0

receive_moments = (data) ->
  $(".feed-title").text data['title']
  $(".feed-description").text data['description']
  $(".feed-moment").remove()
  moments = data['moments']
  for moment in moments
    moment_li = "<li class=\"feed-moment list-group-item\">
                    <div class=\"moment-time\">#{moment['time']}</div>
                    <div class=\"moment-text\">
                        <pre>#{moment['content']}</pre>
                        </div>
                 </li>
                "
    if earliest_first
      $("#feed-moment-list").append moment_li
    else
      $("#feed-moment-list").prepend moment_li
  $("#refreshing-feed").hide()
  feed_successfully_updated += 1

refresh_feed = (feed_id) ->
  $("#refreshing-feed").show()
  posting = $.post '/grabmoments', feed_id: feed_id
  posting.done receive_moments
  posting.fail (data) ->
    $("#refreshing-feed").text "Error: Could not contact server."
  # Now update the text which allows the user to toggle the feed direction
  toggle_button_text = if earliest_first\
                       then "Show latest first"\
                       else "Show earliest first"
  $('#feed-direction-button').text toggle_button_text
toggle_feed_direction = (feed_id) ->
  earliest_first = not earliest_first
  refresh_feed feed_id
