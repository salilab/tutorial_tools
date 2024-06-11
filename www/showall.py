#!/usr/bin/python3

import cgitb
import traceback
import os
import sys
import glob
import json
import yaml

IMP_STABLE_RELEASE = '2.20.2'


def _filter_repo_name(name):
    # Special case the original imp_tutorial repository
    if name == 'imp_tutorial':
        return 'rnapolii_stalk'
    if name.startswith('imp_'):
        name = name[4:]
    if name.endswith('_tutorial'):
        name = name[:-9]
    return name


class Tutorial(object):
    def __init__(self, name, metadata):
        self.name, self.metadata = name, metadata
        self._deps = frozenset(_filter_repo_name(x)
                               for x in metadata.get('depends', []))

    def __lt__(self, other):
        # Simple ordering of tutorials:
        # if one tutorial is explicitly listed as depending on another, it
        # is ordered after the other; otherwise, tutorials without dependencies
        # are listed first
        if other.name in self._deps:
            return False
        elif self.name in other._deps:
            return True
        else:
            return len(self._deps) < len(other._deps)


class Page(object):
    def display(self):
        self.print_header()
        self.show_tutorials()
        self.print_footer()

    def show_tutorials(self):
        print('<div style="padding-bottom: 1.7em"></div>')
        print('<div class="header">')
        print('<div class="headertitle">')
        print('<div class="title">IMP Tutorial Index</div>')
        print('</div></div>')
        print('<div class="contents">')
        print('<div class="textblock">')
        self.print_tutorial_list("*/build.json", prefix='')
        self.print_tutorial_list("*/*/build.json",
                       prefix="""
<h2>Tutorials for IMP nightly build</h2>
<p>These tutorials demonstrate new features of IMP that are not in the
most recent stable release. They will only work with a recent
<a href="/download.html#develop">nightly build</a> of IMP, or IMP
<a href="/nightly/doc/manual/installation.html#installation_source">compiled
from source code</a> from the git <tt>develop</tt> branch.
</p>
""")
        print("</div></div></div>")

    def print_tutorial_list(self, jsonglob, prefix=None):
        jsons = glob.glob(jsonglob)
        ts = []
        for pth in jsons:
            dirname = os.path.dirname(pth)
            metadata = yaml.safe_load(
                open(os.path.join(dirname, 'metadata.yaml')))
            build = json.load(open(os.path.join(dirname, 'build.json')))
            if metadata.get('show_in_index', None) is False:
                continue
            ts.append(Tutorial(dirname, metadata))
        if ts:
            print(prefix)
            print('<dl class="tutorials">')
            for t in sorted(ts):
                print('<dt><a href="//integrativemodeling.org/tutorials/%s/">'
                      '%s</a></dt>' % (t.name, t.metadata['title']))
                print('<dd>%s</dd>' % t.metadata.get('description', ''))
            print("</dl>")

    def print_header(self):
        print('Content-type: text/html')
        print('X-Robots-Tag: noindex, nofollow\n\n')

        print("""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8">
<link href="//integrativemodeling.org/%(stable)s/doc/manual/tabs.css" rel="stylesheet" type="text/css"/>
<link href="//integrativemodeling.org/%(stable)s/doc/manual/doxygen.css" rel="stylesheet" type="text/css"/>
<link href="//integrativemodeling.org/%(stable)s/doc/manual/salilab-doxygen.css" rel="stylesheet" type="text/css"/>
<link href="//integrativemodeling.org/imp.css" rel="stylesheet" type="text/css"/>
<script type='text/javascript'>
  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-44570008-3', 'salilab.org');
  ga('send', 'pageview');
</script>

<title>IMP Tutorial Index</title>
</head>

<body>
<div id="impnav">
   <table class="imptnav">
      <tr>
         <td><a href="//integrativemodeling.org/">
             <img src="//integrativemodeling.org/images/the_imp.png" height="60" alt="IMP logo"></a></td>
         <td>
            <div id="implinks">
             <ul>
               <li><a href="//integrativemodeling.org/">home</a></li>
               <li><a href="//integrativemodeling.org/about.html">about</a></li>
               <li><a href="//integrativemodeling.org/news.html">news</a></li>
               <li><a href="//integrativemodeling.org/download.html">download</a></li>
               <li><a href="//integrativemodeling.org/doc.html" title="Manual, tutorials, and reference guide">doc</a></li>
               <li><a href="https://github.com/salilab/imp" title="Source code, maintained at GitHub">source</a></li>
               <li><a href="//integrativemodeling.org/systems/" title="Applications of IMP to real biological systems">systems</a></li>
               <li><a href="//integrativemodeling.org/nightly/results/" title="Results of IMP's internal test suite">tests</a></li>
               <li><a href="https://github.com/salilab/imp/issues" title="Report a bug in IMP">bugs</a></li>
               <li><a href="//integrativemodeling.org/contact.html" title="Mailing lists and email">contact</a></li>
           </ul>
            </div>
         </td>
      </tr>
   </table>
</div>

<div id="impheaderline">
</div>

<div id="container">

<div id="top">
  <div id="navrow1" class="tabs">
    <ul class="tablist">
      <li><a href="//integrativemodeling.org/%(stable)s/doc/manual/">IMP Manual</a></li>
      <li><a href="//integrativemodeling.org/%(stable)s/doc/ref/">Reference Guide</a></li>
      <li><a href="//integrativemodeling.org/tutorials/">Tutorial Index</a></li>
    </ul>
  </div>
</div>
""" % {'stable': IMP_STABLE_RELEASE})

    def print_footer(self):
        print("""
<h2>Writing new tutorials</h2>
<p>To write a new tutorial, follow
<a href="https://github.com/salilab/tutorial_tools">these instructions</a>.
</p>

</body>
</html>
""")


def email_error(email_to, email_from, exc_info):
    import smtplib
    import email.utils
    from email.mime.text import MIMEText
    text = "".join(traceback.format_exception(*exc_info))
    msg = MIMEText(text)
    msg['Subject'] = 'Error in IMP tutorial index CGI script'
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['From'] = email_from
    msg['To'] = email_to
    s = smtplib.SMTP()
    s.connect()
    s.sendmail(email_from, [email_to], msg.as_string())
    s.close()


def main():
    os.chdir('..')
    t = Page()
    t.display()

if __name__ == '__main__':
    try:
        main()
    except:
        # Don't email if we're running from the command line (testing)
        if sys.argv[0].startswith('./'):
            raise
        else:
            email_error('ben@salilab.org', 'root@salilab.org', sys.exc_info())
            print(cgitb.reset())
            print("<p>Sorry, but an error was detected. We have been " \
                  "notified of the problem and will fix it shortly.</p>")
