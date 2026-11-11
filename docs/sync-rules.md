# The sync rules

What lastread does with your books, as rules. Each rule has a
name (B1, H5, ...) and the tests that hold it in place; a test
(`tests/test_rules_document.py`) fails when a rule here names no test, or a
test that does not exist. So this page cannot promise something the code is
not held to.

Three sources of truth, each for its own part:

- **The Kobo** knows what you read: progress, finished or not, when.
- **You** decide which books sync, and can overrule the Kobo per book (on
  the page, or by editing the book on Hardcover).
- **Hardcover** is where it ends up. The only things taken back from it
  are your own edits there.

## Which books

- **B1** Only books that were opened count. A book nobody touched is not
  listed and not sent.
  Tests: `tests/test_core.py::test_history_off_then_new_books_auto`
- **B2** The first time a Kobo is read, every book already on it is
  *history*: sync Off until you switch it on. Nothing from before goes to
  Hardcover by itself.
  Tests: `tests/test_core.py::test_history_off_then_new_books_auto`
- **B3** A book first opened on that Kobo after the first import is *new*:
  it syncs by itself (Auto), and can be switched off. Also a book the Kobo
  listed before with someone else's progress, on a shared Kobo account: it
  is new from the day you open it on yours. Not when it was finished
  already, when you set something for it, or when you opened it on another
  Kobo of yours before: those stay as they were.
  Tests: `tests/test_core.py::test_history_off_then_new_books_auto`,
  `tests/test_rules.py::test_a_book_known_from_the_account_is_new_once_it_is_opened_on_this_kobo`,
  `tests/test_rules.py::test_a_book_opened_on_another_kobo_before_is_not_new_on_this_one`
- **B4** A reader's choices and books are their own. Nothing one reader
  does reaches another reader's books.
  Tests: `tests/test_core.py::test_modes_and_dry_run_actions`,
  `tests/test_web.py::test_filters_never_leak_other_readers`
- **B5** A book that is gone from the Kobo stays as it was: still listed,
  still on Hardcover. Deleting a book from the Kobo never removes anything.
  Tests: `tests/test_rules.py::test_a_book_gone_from_the_kobo_stays_as_it_was`
- **B6** Reading the same Kobo again changes nothing, and reading time is
  not counted twice.
  Tests: `tests/test_rules.py::test_importing_the_same_kobo_twice_changes_nothing`
- **B7** Reading time counts only for books opened on this Kobo. The Kobo
  account's reading time is shared by everyone on the account; the rest of
  the family's reading is not yours.
  Tests: `tests/test_stats.py::test_minutes_only_count_books_opened_on_this_device`
- **B8** Books are kept per reader and per Kobo: the same book on two
  Kobos is listed for each.
  Tests: `tests/test_rules.py::test_the_same_book_on_two_kobos_is_two_rows`

## What Hardcover gets

- **H1** Dry run until you go live under Settings: books are matched and
  the plan is shown, nothing is written to Hardcover.
  Tests: `tests/test_hardcover.py::test_dry_run_matches_but_writes_nothing`
- **H2** A book the Kobo calls finished becomes *Read*, with the Kobo's
  finish date. A finished book that was opened again stays *Read* on the
  old date; say *Rereading* on the page when it is a real re-read.
  Tests: `tests/test_core.py::test_finished_rule_and_state_override`
- **H3** A book being read becomes *Currently reading*, with progress. A
  book the Kobo still calls unread, but with progress, is being read.
  Tests: `tests/test_core.py::test_modes_and_dry_run_actions`,
  `tests/test_rules.py::test_a_book_with_progress_is_being_read_whatever_the_kobo_calls_it`,
  `tests/test_hardcover.py::test_live_sends_one_read_entry_per_book_and_is_idempotent`
- **H4** The start date is the day the book was first seen being read. A
  book that was already being read when it was first seen has no start
  date: it is not known.
  Tests: `tests/test_rules.py::test_the_start_date_is_the_day_the_book_was_first_seen_being_read`
- **H5** Progress is the Kobo's number, also when it went down (you
  paged back, or started again).
  Tests: `tests/test_rules.py::test_progress_is_the_kobos_number_also_when_it_went_down`
- **H6** Progress goes to Hardcover as a page in the edition on your
  shelf: the Kobo's percentage of that edition's pages, rounded to the
  nearest page, never outside the book. An edition without a page count
  gets the status and no progress.
  Tests: `tests/test_rules.py::test_progress_is_pages_of_the_edition_rounded_and_within_the_book`,
  `tests/test_rules.py::test_without_a_page_count_the_status_is_sent_and_no_progress`
- **H7** Nothing is sent when nothing changed. Progress is sent when it
  moved by a percent or more.
  Tests: `tests/test_hardcover.py::test_live_sends_one_read_entry_per_book_and_is_idempotent`,
  `tests/test_core.py::test_modes_and_dry_run_actions`
- **H8** A book gets one read-through on Hardcover (the one Hardcover
  makes when a book lands on the shelf is used). Only a re-read you
  declared adds a second one.
  Tests: `tests/test_hardcover.py::test_reread_of_a_shelf_book_adds_a_read_but_a_new_book_never_gets_two`
- **H9** Per book you can overrule the Kobo on the page: *Finished* (with a
  date), *Rereading*, *Want to read*, *Did not finish*. *Want to read* and
  *Did not finish* are left alone on Hardcover, with no progress, until
  you set the book back to *Follow Kobo*.
  Tests: `tests/test_core.py::test_finished_rule_and_state_override`,
  `tests/test_hardcover.py::test_want_to_read_and_dnf_are_left_alone_until_follow_kobo`,
  `tests/test_hardcover.py::test_changed_finish_date_on_the_page_is_sent`
- **H10** *Remove from Hardcover* on the page takes the book off your
  shelf there and switches its sync off.
  Tests: `tests/test_hardcover.py::test_remove_deletes_and_switches_off`
- **H11** The finish date is the date in the Kobo's own clock, which is
  UTC: a book finished shortly after midnight can carry the day before.
  Tests: `tests/test_rules.py::test_the_finish_date_is_the_kobos_utc_date`

## Matching a Kobo book to a Hardcover book

- **M1** By ISBN first, then by a search on title and author. A book the
  search finds is only taken when a title and an author both agree; a
  doubtful hit is put to you instead.
  Tests: `tests/test_matching.py::test_a_title_agrees_exactly_as_a_part_or_as_a_start`,
  `tests/test_matching.py::test_an_author_has_to_agree_and_may_be_any_name_the_kobo_lists`,
  `tests/test_hardcover.py::test_dry_run_matches_but_writes_nothing`
- **M2** A book without a match is never sent. It is looked up once and
  then waits for you. When a newer version of the tool has other rules for
  matching, it is looked up once more.
  Tests: `tests/test_rules.py::test_an_unmatched_book_is_never_sent`,
  `tests/test_matching.py::test_a_waiting_book_gets_one_more_look_when_the_rules_have_changed`
- **M3** A match you chose is kept: not looked up again, not replaced.
  Tests: `tests/test_rules.py::test_a_match_the_reader_chose_is_kept`
- **M4** The edition: the one with the Kobo's ISBN if it is an ebook, else
  an ebook edition in the book's language, else any ebook edition, else
  the one with the Kobo's ISBN, else Hardcover's default.
  Tests: `tests/test_hardcover.py::test_edition_choice_order`,
  `tests/test_hardcover.py::test_ebook_edition_is_chosen_and_set_on_the_shelf`,
  `tests/test_hardcover.py::test_existing_shelf_edition_is_a_baseline_then_replaced_by_the_rule`
- **M5** An edition you chose on Hardcover is taken over and never
  replaced.
  Tests: `tests/test_hardcover.py::test_edition_chosen_on_hardcover_is_adopted_and_never_overwritten`
- **M6** A title agrees when it is the book's title, or the book's title
  without its subtitle or without a series name in front. A leading article
  (the, a, de, het, een) does not count. A title that only starts the same
  is believed of the search's first hit alone: further down it may as well
  be the next book of a series.
  Tests: `tests/test_matching.py::test_a_title_agrees_exactly_as_a_part_or_as_a_start`
- **M7** A translation is taken when Hardcover itself lists the Kobo's
  title among the other titles of the book, and an author agrees. A
  translation Hardcover does not list waits for you; it is never guessed
  from the author alone.
  Tests: `tests/test_matching.py::test_a_translation_is_known_by_the_titles_hardcover_lists_for_the_book`,
  `tests/test_matching.py::test_a_translation_matches_by_itself_and_what_is_kept_for_the_reader_is_small`
- **M8** The author may be any name the Kobo lists for the book: it lists
  translators and illustrators as well, sometimes first.
  Tests: `tests/test_matching.py::test_an_author_has_to_agree_and_may_be_any_name_the_kobo_lists`
- **M9** The first five hits of a search are looked at. The exact title
  goes before a partial one. When several books agree equally, the
  search's first hit is taken if it is one of them (Hardcover often has one
  book twice); otherwise you choose.
  Tests: `tests/test_matching.py::test_which_hit_is_taken`
- **M10** A book you put on the Kobo yourself (sideloaded) is looked up by
  the ISBN its own EPUB file names, when the Kobo keeps none for it; when
  the book names none either, by a 13-digit ISBN in its file name. Only
  an ISBN with a valid check digit is taken, a file name with two different
  ones says nothing, never more than the book's
  package document is read, and the file is only read. A book that was
  waiting for you gets one more look when its ISBN turns up; a match you
  chose stays (M3).
  Tests: `tests/test_epub.py::test_an_epub_names_its_isbn_and_other_numbers_are_not_taken_for_one`,
  `tests/test_epub.py::test_the_isbn_in_the_file_name_when_the_book_names_none`,
  `tests/test_tokobo.py::test_the_folders_list_has_the_isbn_of_the_name_also_for_a_book_read_before`,
  `tests/test_epub.py::test_a_book_put_on_the_kobo_by_hand_gets_the_isbn_its_own_file_names`,
  `tests/test_epub.py::test_a_waiting_book_is_looked_up_again_when_its_isbn_arrives`,
  `tests/test_local.py::test_a_book_put_on_the_kobo_by_hand_is_found_by_the_isbn_in_its_file`

## Several Kobo books that are one book on Hardcover

Two editions, a sample and the book, or the same book on two Kobos.

- **C1** One of them speaks for the book on Hardcover: the one read last.
  There is one shelf entry and one read-through, and the copies do not
  overwrite each other at every sync.
  Tests: `tests/test_rules.py::test_of_two_copies_of_one_hardcover_book_the_one_read_last_speaks`
- **C2** When another copy is read later, that one takes over, on the same
  shelf entry.
  Tests: `tests/test_rules.py::test_the_other_copy_takes_over_once_it_is_read_later`
- **C3** A copy that is switched off, or was only opened and not read,
  does not speak.
  Tests: `tests/test_rules.py::test_a_copy_that_is_switched_off_or_unread_does_not_speak`
- **C4** The same book on two Kobos follows the Kobo it was read on last;
  an old Kobo in a drawer does not pull the progress back.
  Tests: `tests/test_rules.py::test_the_same_book_on_two_kobos_follows_the_kobo_it_was_read_on_last`
- **C5** The page says so on the copy that does not speak.
  Tests: `tests/test_web.py::test_a_copy_that_does_not_speak_for_its_hardcover_book_says_so`
- **C6** A book you match by hand to a book that already syncs joins it,
  instead of becoming a second shelf entry.
  Tests: `tests/test_rules.py::test_a_book_matched_by_hand_to_a_book_already_synced_joins_it`
- **C7** An edit you make on Hardcover is taken over by the copy that
  speaks. Another edition keeps what its Kobo says about it, for when it is
  read again. The same book on two Kobos is one book: the edit holds for
  it on both.
  Tests: `tests/test_rules.py::test_an_edit_on_hardcover_is_taken_over_by_the_copy_that_speaks`,
  `tests/test_rules.py::test_an_edit_on_hardcover_reaches_the_book_on_every_kobo`
- **C8** Sync, State and the Hardcover match are set per book, not per
  Kobo. The page lists the same book on two Kobos once, as the Kobo it was
  read on last says it, and what you set there holds on both. A book that
  comes along on another Kobo later keeps what was set for it, also a
  match you chose by hand.
  Tests: `tests/test_rules.py::test_a_book_that_comes_on_a_second_kobo_keeps_what_was_set_for_it`,
  `tests/test_web.py::test_the_same_book_on_two_kobos_is_one_book_on_the_page`
- **C9** Where an earlier version let the two Kobos' copies of a book
  differ, the one read last decides, once, at the first start of a version
  with C8.
  Tests: `tests/test_rules.py::test_a_book_set_apart_on_two_kobos_before_is_made_one_book_again`

## What you change on Hardcover

Looked at when a sync runs, and only for books this tool put on your shelf
or found there.

- **E1** Marked *Read* there, or given another finish date: the book is
  pinned as finished on that date. Later reading on the Kobo does not undo
  it.
  Tests: `tests/test_hardcover.py::test_read_on_hardcover_becomes_a_pinned_finished_state`
- **E2** A finished book set back to *Currently reading* there: a re-read.
  Tests: `tests/test_hardcover.py::test_finished_book_set_to_reading_on_hardcover_is_a_reread`
- **E3** *Want to read* or *Did not finish* there: left alone.
  Tests: `tests/test_hardcover.py::test_want_to_read_and_dnf_are_left_alone_until_follow_kobo`
- **E4** Taken off the shelf there: sync goes off for that book, for every
  copy of it, and it is not added again. The match is kept.
  Tests: `tests/test_hardcover.py::test_removed_on_hardcover_switches_sync_off_and_is_not_added_again`,
  `tests/test_rules.py::test_a_book_taken_off_the_shelf_on_hardcover_switches_every_copy_off`,
  `tests/test_rules.py::test_a_copy_that_never_spoke_goes_off_with_the_book_too`
- **E5** A state you set on the page after the last sync wins over an edit
  made on Hardcover in the same period.
  Tests: `tests/test_hardcover.py::test_state_set_on_the_page_wins_over_an_edit_on_hardcover`
- **E6** Progress is never taken from Hardcover. The Kobo knows where you
  are; a page number typed in on Hardcover is replaced the next time the
  Kobo's progress moves.
  Tests: `tests/test_rules.py::test_progress_set_on_hardcover_is_not_taken_over`

## When something goes wrong

- **F1** A book that Hardcover refuses does not stop the others. Its error
  is shown with the book, nothing is recorded as sent, and it is tried
  again at the next sync.
  Tests: `tests/test_rules.py::test_one_failing_book_does_not_stop_the_others_and_is_tried_again`
- **F2** Hardcover out of reach: the run fails and says so, what the Kobo
  said is kept, and the next sync sends what was waiting.
  Tests: `tests/test_rules.py::test_hardcover_out_of_reach_fails_the_run_and_loses_nothing`,
  `tests/test_local.py::test_hardcover_trouble_is_said_and_the_books_are_still_imported`
- **F8** Trouble that is the same for every book stops the run at the
  first book: no connection, too many requests, a token Hardcover does not
  accept or that lacks a permission. What was sent before it stays sent.
  Tests: `tests/test_rules.py::test_trouble_that_is_the_same_for_every_book_stops_the_run_at_the_first_one`
- **F9** A request that failed is tried again, three times at most, when
  that cannot do harm. A question always. A change only when Hardcover
  says it was not carried out (asked to slow down, or "temporarily
  unavailable"); after a time-out or a server error nobody knows, so it is
  not sent twice and the next sync looks at the shelf first. Someone
  waiting at the page (testing a token, searching for a match) gets one
  try and an answer.
  Tests: `tests/test_hardcover_client.py::test_asked_to_slow_down_it_waits_as_long_as_asked_and_tries_again`,
  `tests/test_hardcover_client.py::test_a_question_is_asked_again_when_hardcover_is_in_trouble`,
  `tests/test_hardcover_client.py::test_a_change_is_not_sent_twice_when_nobody_knows_whether_it_happened`,
  `tests/test_hardcover_client.py::test_no_answer_at_all`,
  `tests/test_hardcover_client.py::test_a_person_waiting_at_the_page_gets_one_try`
- **F10** When the day's requests to Hardcover are used up, the run stops
  and says so instead of waiting for hours.
  Tests: `tests/test_hardcover_client.py::test_when_the_days_requests_are_used_up_it_stops_instead_of_waiting_for_hours`
- **F11** A token Hardcover does not accept, or that lacks a permission, is
  said in those words, with what to do. It is not tried again.
  Tests: `tests/test_hardcover_client.py::test_a_token_hardcover_does_not_accept_is_said_once_and_not_tried_again`,
  `tests/test_hardcover_client.py::test_a_token_without_the_permission_names_what_is_missing`
- **F12** The shelf is fetched whole, however large, and counted: an answer
  that is cut off, or holds fewer books than Hardcover says the shelf has,
  is an error. It is never read as "you took these books off".
  Tests: `tests/test_hardcover_client.py::test_a_shelf_larger_than_one_page_is_fetched_whole`,
  `tests/test_hardcover_client.py::test_a_shelf_that_comes_back_short_is_an_error_never_a_shorter_shelf`,
  `tests/test_hardcover_client.py::test_an_answer_that_is_cut_off_or_not_hardcovers_is_not_taken_for_data`,
  `tests/test_hardcover_client.py::test_a_page_that_fails_halfway_fails_the_shelf`
- **F13** A shelf that holds none of the books that sync (three or more)
  is not believed: nothing is switched off, and the run says so. It is
  another account's shelf, or a token that may not read yours.
  Tests: `tests/test_rules.py::test_a_shelf_without_any_of_our_books_switches_nothing_off`
- **F14** Once books are on a Hardcover shelf, the tool remembers whose
  shelf it is. A connection to another Hardcover account stops the sync
  before anything is sent or switched off, from the first book, and says
  which two accounts they are. To move to the other account on purpose,
  start over (Settings, or `token --start-over`): what was put on the old
  shelf is forgotten here, the old shelf stays as it is, and the next sync
  fills the new one. Sync, State and matches are kept.
  Tests: `tests/test_rules.py::test_a_token_for_another_account_sends_and_switches_off_nothing`,
  `tests/test_rules.py::test_the_account_is_bound_once_books_are_on_its_shelf`,
  `tests/test_accounts.py::test_a_connection_to_another_account_offers_to_start_over_on_it`
- **F3** A run that is cut off after Hardcover took a book, and before
  that was written down here, does not add the book a second time: the
  next run finds it on the shelf.
  Tests: `tests/test_rules.py::test_a_run_cut_off_after_hardcover_took_the_book_does_not_add_it_twice`
- **F4** One sync at a time. A second one started meanwhile leaves quietly.
  Tests: `tests/test_computer.py::test_a_second_sync_at_the_same_time_leaves_quietly`
- **F5** A Kobo unplugged halfway is said, and nothing is left half done.
  Tests: `tests/test_local.py::test_a_kobo_unplugged_halfway`
- **F6** Plugging in again without having read does nothing: no import,
  nothing sent, nothing written to the Kobo.
  Tests: `tests/test_local.py::test_plug_in_dry_run_live_collection_and_then_nothing`,
  `tests/test_computer.py::test_plug_in_upload_then_collection_then_nothing`
- **F7** Without a Kobo, a sync you ask for still does the Hardcover half
  (local mode).
  Tests: `tests/test_local.py::test_without_a_kobo_only_the_hardcover_half_runs`

## The collection on the Kobo

Optional: with a collection name under Settings, the Kobo gets a collection
of the books that sync. This is the only thing ever written to the Kobo.

- **K1** The collection holds exactly the books that sync, and that are on
  this Kobo; with the books of your EPUB folder when you choose that (P8).
  Tests: `tests/test_collection.py::test_one_in_one_out_and_ids_that_are_not_books_here_are_skipped`,
  `tests/test_upload.py::test_collection_endpoint_lists_the_syncing_books`
- **K2** Nothing is written when the collection is already right, and
  nothing is created for an empty list.
  Tests: `tests/test_collection.py::test_create_then_the_same_list_again_writes_nothing`,
  `tests/test_collection.py::test_with_a_copy_to_look_at_the_kobos_file_is_not_opened_when_nothing_changes`,
  `tests/test_collection.py::test_an_empty_list_creates_nothing`
- **K3** Only the collection this tool made is touched, and it is known by
  the id it was given, not by its name. A collection of yours with the same
  name is left alone. Each Kobo's collection has an id of its own, so a
  second Kobo gets the same collection and both are kept.
  Tests: `tests/test_collection.py::test_a_collection_of_that_name_that_is_not_ours_is_left_alone`,
  `tests/test_collection.py::test_ours_stays_ours_only_through_the_remembered_id`,
  `tests/test_collection.py::test_ours_is_known_by_its_id_not_by_its_name`,
  `tests/test_collection.py::test_a_second_kobo_gets_its_own_collection_of_that_name_and_both_stay_ours`
- **K4** The collection is the tool's: a book you add to it by hand on the
  Kobo is taken out again at the next sync. Keep your own collections for
  your own lists.
  Tests: `tests/test_collection.py::test_a_book_added_by_hand_on_the_kobo_is_taken_out_again`
- **K5** Another name under Settings: at the next plug-in the old
  collection is taken off the Kobo and the new one made, in one write with
  one backup. When the new name is refused (a collection of yours has it),
  nothing is written and the old one stays. A cleared name: the collection
  is taken off. Nobody else's collection is touched.
  Tests: `tests/test_collection.py::test_a_collection_made_under_another_name_is_taken_off_again`,
  `tests/test_collection.py::test_another_name_is_one_write_with_one_backup`,
  `tests/test_collection.py::test_another_name_that_is_refused_leaves_the_old_collection`,
  `tests/test_collection.py::test_a_cleared_name_takes_every_collection_of_ours_off_and_nobody_elses`,
  `tests/test_local.py::test_a_new_collection_name_replaces_the_old_collection_and_a_cleared_one_removes_it`,
  `tests/test_computer.py::test_in_server_mode_a_cleared_name_removes_the_collection_but_a_server_out_of_reach_does_not`
- **K6** When the server cannot be asked what the collection should be, the
  Kobo is left as it is.
  Tests: `tests/test_computer.py::test_in_server_mode_a_cleared_name_removes_the_collection_but_a_server_out_of_reach_does_not`
- **K7** A Kobo whose database is not one this tool was tried on is not
  written to. Its books still sync to Hardcover.
  Tests: `tests/test_collection.py::test_an_untested_database_version_is_refused_unless_asked_for`,
  `tests/test_collection.py::test_a_database_that_lacks_what_is_written_is_refused_even_when_asked_for`,
  `tests/test_collection.py::test_a_new_column_that_must_be_filled_in_is_refused`,
  `tests/test_collection.py::test_removing_the_old_collection_obeys_the_gate_and_looks_at_the_copy_first`,
  `tests/test_computer.py::test_an_untested_kobo_still_syncs_but_its_collection_is_left_alone`
- **K8** Before every write the Kobo's database is copied; the last three
  copies are kept.
  Tests: `tests/test_collection.py::test_only_the_last_three_backups_are_kept`
- **K9** A write happens completely or not at all, also when the tool dies
  or the Kobo is pulled out in the middle. A write that did reach the Kobo
  is known to be this tool's from that moment, so the next sync carries on
  with it, also when the Kobo was gone before the tool could look again.
  Tests: `tests/test_collection.py::test_a_failure_inside_the_write_changes_nothing`,
  `tests/test_collection.py::test_a_process_that_dies_in_the_middle_of_the_write_changes_nothing`,
  `tests/test_collection.py::test_a_first_write_that_fails_does_not_remember_a_collection`,
  `tests/test_collection.py::test_a_kobo_that_disappears_right_after_the_write_is_reported_with_the_backup`,
  `tests/test_collection.py::test_a_write_that_landed_but_was_not_confirmed_is_still_this_tools_collection`,
  `tests/test_collection.py::test_a_kobo_unplugged_during_the_write_says_so`
- **K10** Books that are not on this Kobo are skipped, and so are books you
  put on the Kobo yourself (sideloaded): they can sync to Hardcover, but
  they are not put in the collection. The one exception is the books this
  tool put in its own folder on the Kobo, when you ask for them (P8).
  Tests: `tests/test_collection.py::test_one_in_one_out_and_ids_that_are_not_books_here_are_skipped`

## Books put on the Kobo

Only when you chose a folder (`lastread to-kobo FOLDER`). The Kobo finds
the books itself after the eject; at the next plug-in they are books like
any other you put on it yourself (M10).

- **P1** Only the EPUBs of the folder you chose, and the folders in it;
  nothing when you chose none. Hidden files and folders are left out. They
  go into one folder on the Kobo, `Lastread`, and nowhere else.
  Tests: `tests/test_tokobo.py::test_only_the_books_of_the_folder_you_chose_and_nothing_without_one`,
  `tests/test_tokobo.py::test_choosing_the_folder`
- **P2** A book with DRM (Adobe, Readium LCP, or encrypted otherwise) is not
  copied: it would not open on the Kobo. You are told once, with what to
  use instead. Nothing is decrypted. Hidden fonts are not DRM.
  Tests: `tests/test_tokobo.py::test_only_epubs_and_a_book_with_drm_is_refused_and_said_once`
- **P3** A book goes on each Kobo once, known by its contents, not its
  name. Deleted on the Kobo, it stays deleted; taken out of the folder or
  renamed, it stays on the Kobo. One you already put on the Kobo by hand
  is not put there twice. Another Kobo gets every book of the folder.
  Tests: `tests/test_tokobo.py::test_a_book_goes_on_each_kobo_once_and_a_delete_on_the_kobo_stays`
- **P4** Never over another file: a name the Kobo has already gets a
  number. A character the Kobo's storage cannot hold in a name
  (`< > : " / \ | ? *`) becomes `_`.
  Tests: `tests/test_tokobo.py::test_never_over_another_file_a_name_that_is_taken_gets_a_number`,
  `tests/test_tokobo.py::test_a_name_the_kobo_cannot_hold_goes_with_those_characters_replaced`
- **P5** A book is on the Kobo whole or not at all, also when the Kobo is
  pulled out halfway; what was left half is cleared at the next plug-in.
  A Kobo without room gets nothing half; the books wait, and so they do
  when the Kobo refuses every copy (read-only, for one). A book the Kobo
  refuses for itself is said once, and the books after it still go. A file
  this computer cannot read (a link to a file that is gone, one taken out
  of the folder halfway) is left out and the others still go: the folder's
  list says why, and it is never taken for a Kobo that was unplugged.
  Tests: `tests/test_tokobo.py::test_a_copy_is_whole_or_not_there_also_when_the_kobo_is_pulled_out`,
  `tests/test_tokobo.py::test_a_long_name_goes_and_a_book_the_kobo_will_not_take_is_said_once`,
  `tests/test_tokobo.py::test_a_kobo_that_refuses_every_copy_keeps_the_books_for_next_time`,
  `tests/test_tokobo.py::test_a_file_this_computer_cannot_read_does_not_stop_the_other_books`,
  `tests/test_tokobo.py::test_a_file_gone_from_the_folder_halfway_is_not_the_kobo_unplugged`
- **P6** Only files are written: the Kobo's database is never touched for
  this. In server mode the computer does it, and no book goes to the
  server.
  Tests: `tests/test_tokobo.py::test_only_files_are_written_never_the_database`,
  `tests/test_tokobo.py::test_server_mode_puts_the_books_on_the_kobo_from_this_computer`
- **P7** A plain EPUB goes on the Kobo as kepub when kepubify is there:
  the Mac app's own first, else one installed on this computer (Homebrew
  installs it with Lastread). Kepub is the Kobo's own renderer, with its
  reading statistics. It is converted in a temporary folder here; your own file is
  not touched. A book kepubify cannot convert in five minutes goes as it
  is, and so do all of them without kepubify; the sync's line says which.
  Tests: `tests/test_tokobo.py::test_a_plain_epub_goes_as_kepub_when_kepubify_is_installed`,
  `tests/test_tokobo.py::test_a_book_kepubify_cannot_convert_goes_as_it_is`,
  `tests/test_tokobo.py::test_without_kepubify_the_books_go_as_epub_and_it_is_said_how_to_get_kepub`,
  `tests/test_tokobo.py::test_kepubify_is_found_where_homebrew_puts_it_also_without_it_on_the_path`,
  `tests/test_tokobo.py::test_the_mac_apps_own_kepubify_goes_first`
- **P8** The books in the Kobo's Lastread folder (every book there, also
  one whose file left your folder since) are in no collection of this
  tool's unless you choose otherwise: they can join the collection of the
  books that sync, or have a collection of their own, Lastread unless you
  name it. Chosen with `lastread to-kobo --collection none|synced|own
  [--name NAME]`, or in the Mac app's EPUB Folder. A book joins at the
  plug-in after the one that put it there, once the Kobo has found the
  file. Their own collection is kept by the same rules as the other
  (K1-K9), apart from it: changing one never touches the other, a new
  name takes the old one off, and choosing none takes it off the Kobo. A
  collection of that name that this tool did not make is left alone, and
  that is said. Other sideloaded books stay out (K10).
  Tests: `tests/test_tokobo.py::test_the_folders_books_in_no_collection_with_the_synced_books_or_in_their_own`,
  `tests/test_tokobo.py::test_server_mode_keeps_the_folders_own_collection_on_this_computer`,
  `tests/test_tokobo.py::test_choosing_where_the_folders_books_go`

## What leaves your computer

- **U1** The Kobo account's login tokens are never read and never sent.
  Tests: `tests/test_core.py::test_refuses_tokens_and_non_kobo`
- **U2** In server mode the upload holds the book rows and the reading
  events, nothing else, and the server refuses an upload that holds more.
  Tests: `tests/test_computer.py::test_the_upload_holds_only_what_the_server_reads`,
  `tests/test_upload.py::test_an_upload_with_more_than_the_server_reads_is_refused`

## Known limits

Not bugs, but worth knowing. Each follows from a rule above.

- **Finish dates are UTC dates** (H11). Read until just after midnight and
  Hardcover may show the day before. Set the date on the page (*Finished*,
  with a date) when it matters.
- **No start date for what you were already reading** when the tool first
  saw your Kobo (H4).
- **Two copies of one book** (C1): the copy read last speaks. Opening a
  sample or another edition of a book you finished sets the book to
  *Currently reading* on Hardcover. Switch that copy off on the page if
  that is not what you want.
- **Sideloaded books** are not put in the collection (K10), except the
  books from your EPUB folder when you choose that (P8).
- **The collection is not yours to edit** (K4). Books added by hand are
  taken out again.
- **Edits on Hardcover are seen at the next sync**, not at once: at the
  next plug-in in local mode, within the hour on a server.
- **Progress typed in on Hardcover is not kept** (E6).
- **Emptying your Hardcover shelf by hand** (F13): when every book that
  syncs is gone from the shelf at once, the tool does not believe it and
  stops. Switch those books off on the page and it carries on.
- **A large first sync can take more than a day**: Hardcover allows 5000
  requests a day, and a book costs about four. The run stops when the day
  is used up and carries on at the next sync (F10).
