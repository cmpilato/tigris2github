#!/usr/bin/env python
import sys
from github import Github
import xml.etree.ElementTree as ET
import base64

############################################################################
#
# CONFIGURATION
#

GITHUB_USERNAME='YOUR_USERNAME_HERE'
GITHUB_PASSWORD='YOUR_PASSWORD_HERE'
GITHUB_ORGANIZATION='YOUR_ORGANIZATION_HERE'
GITHUB_REPOSITORY='YOUR_REPOSITORY_HERE'
ISSUEZILLA_XML_EXPORT_FILE='/path/to/exported_issues.xml'

#
############################################################################


class _item:
  """Generic thing"""
  def __init__(self, **kw):
    vars(self).update(kw)


def getchildtext(item, child_name):
  """Get the text of a named ElementTree child of ITEM."""
  child = item.find(child_name)
  return child is not None and child.text or ''


def mdquote(s):
  """Turn a block of text into a Markdown blockquote section"""
  return '\n'.join(map(lambda x: '  ' + x, s.split('\n')))


def parse_issues_xml():
  """Parse the XML issues export file, returning an array of _items
  representing issues."""
  issues = []
  for iz in ET.parse(ISSUEZILLA_XML_EXPORT_FILE).getroot():
    issue = _item(id=getchildtext(iz, 'issue_id'),
                  date=getchildtext(iz, 'creation_ts'),
                  summary=getchildtext(iz, 'short_desc'),
                  version=getchildtext(iz, 'version'),
                  component=getchildtext(iz, 'component'),
                  subcomponent=getchildtext(iz, 'subcomponent'),
                  reporter=getchildtext(iz, 'reporter'),
                  milestone=getchildtext(iz, 'target_milestone'),
                  type=getchildtext(iz, 'issue_type'),
                  keywords=map(lambda x: x.strip(),
                               getchildtext(iz, 'keywords').split(',')),
                  ccs=map(lambda x: x.text, iz.findall('cc')),
                  comments=[],
                  attachments=[])
    comments = iz.findall('long_desc')
    issue.description = getchildtext(comments.pop(0), 'thetext')
    for long_desc in comments:
      issue.comments.append(
          _item(username=getchildtext(long_desc, 'who'),
                date=getchildtext(long_desc, 'issue_when'),
                comment=getchildtext(long_desc, 'thetext')))
    for attachment in iz.findall('attachment'):
      data = getchildtext(attachment, 'data')
      encoded = True
      try:
        data = unicode(base64.decodestring(data))
        encoded = False
      except:
        pass
      issue.attachments.append(
          _item(filename=getchildtext(attachment, 'filename'),
                description=getchildtext(attachment, 'desc'),
                date=getchildtext(attachment, 'date'),
                username=getchildtext(attachment, 'submitting_username'),
                encoded=encoded,
                data=data))
    issues.append(issue)
  return issues


def decorate_issues(issues):
  """Generate the Github title, labels, and body for the issues."""

  for issue in issues:
    title = "%s [Tigris #%s]" % (issue.summary, issue.id)
    labels = filter(None, [{'ENHANCEMENT': 'enhancement',
                            'FEATURE': 'enhancement',
                            'DEFECT': 'bug',
                            'PATCH': 'patch',
                            }.get(issue.type)] + issue.keywords)
    comments = ''
    for comment in issue.comments:
      comments = comments + """### %s by %s
  
%s

""" % (comment.date, comment.username, mdquote(comment.comment))
    attachments = ''
    for attachment in issue.attachments:
      attachments = attachments + """### %s - %s
_Posted %s by %s_

%s

%s
""" % (attachment.filename, attachment.description,
       attachment.date, attachment.username,
       mdquote(attachment.data),
       attachment.encoded and '_encoding=base64_\n' or '')
    body = """## Description

%s

## Metadata Imported from Tigris (Issue %s)

  * **Creation Date**: %s
  * **Reporter**: %s
  * **Subcomponent**: %s
  * **Version**: %s
  * **Milestone**: %s
  * **Keywords**: %s
  * **Cc**: %s

""" % (mdquote(issue.description), issue.id, issue.date, issue.reporter,
       issue.subcomponent, issue.version, issue.milestone,
       ', '.join(issue.keywords), ', '.join(issue.ccs))
    if comments:
      body = body + """## Comments

%s

""" % (comments)
    if attachments:
      body = body + """## Attachments

%s

""" % (attachments)
    issue.github_title = title
    issue.github_labels = labels
    issue.github_body = body


if __name__ == "__main__":
  issues = parse_issues_xml()
  decorate_issues(issues)
  g = Github(GITHUB_USERNAME, GITHUB_PASSWORD)
  org = g.get_organization(GITHUB_ORGANIZATION)
  repo = org.get_repo(GITHUB_REPOSITORY)
  milestone_map = {}
  for milestone in repo.get_milestones():
    milestone_map[milestone.title] = milestone
  label_map = {}
  for label in repo.get_labels():
    label_map[label.name] = label
  for issue in issues:
    issue.github_milestone = milestone_map.get(issue.milestone)
    sys.stdout.write("Importing issue %s - %s ..." % (issue.id, issue.summary))
    try:
      repo.create_issue(issue.github_title,
                        body=issue.github_body,
                        milestone=issue.github_milestone,
                        labels=map(lambda x: label_map.get(x),
                                   issue.github_labels))
      sys.stdout.write("DONE.\n")
    except Exception, e:
      sys.stdout.write("FAILED: %s\n" % (str(e)))
  
